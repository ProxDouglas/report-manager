import asyncio
import logging
import os
import signal
import time

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.metrics import increment, set_gauge
from app.db.enums import ExecutionStatus
from app.db.models import Execution, WorkerHeartbeat, utc_now
from app.db.session import SessionLocal
from app.services.execution_service import claim_next_execution, run_claimed_execution
from app.services.retention import run_retention

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("report-manager.worker")


async def run() -> None:
    """Processa execuções sob demanda sem bloquear a API HTTP."""

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    settings = get_settings()
    last_retention_run = 0.0
    last_heartbeat = 0.0
    worker_name = os.environ.get("REPORT_MANAGER_WORKER_NAME", "report-manager-worker")

    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(stop_signal, stop_event.set)

    logger.info("worker iniciado; aguardando a fila de execuções")
    while not stop_event.is_set():
        database = SessionLocal()
        try:
            if time.monotonic() - last_heartbeat >= 10:
                heartbeat = database.get(WorkerHeartbeat, worker_name)
                if heartbeat is None:
                    heartbeat = WorkerHeartbeat(worker_name=worker_name, status="ATIVO")
                    database.add(heartbeat)
                heartbeat.last_seen_at = utc_now()
                heartbeat.status = "ATIVO"
                heartbeat.worker_metadata = {"runtime": "docker-or-process"}
                database.commit()
                last_heartbeat = time.monotonic()
                set_gauge("report_manager_worker_up", 1, {"worker": worker_name})
            if time.monotonic() - last_retention_run >= 300:
                try:
                    run_retention(database, settings)
                except SQLAlchemyError:
                    database.rollback()
                    logger.exception("falha temporária na retenção")
                last_retention_run = time.monotonic()
            try:
                queued = database.scalar(
                    select(func.count(Execution.id)).where(
                        Execution.status == ExecutionStatus.CREATED
                    )
                )
                set_gauge("report_manager_queue_depth", float(queued or 0))
                execution = claim_next_execution(database)
            except SQLAlchemyError:
                logger.exception("falha temporária ao consultar a fila")
                increment("report_manager_worker_errors_total")
                await asyncio.sleep(2)
                continue
            if execution:
                increment("report_manager_executions_claimed_total")
                logger.info("execução iniciada", extra={"execution_id": str(execution.id)})
                run_claimed_execution(database, settings, execution)
            else:
                await asyncio.sleep(1)
        finally:
            database.close()
    logger.info("worker encerrado")


if __name__ == "__main__":
    asyncio.run(run())
