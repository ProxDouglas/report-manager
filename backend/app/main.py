import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from starlette.responses import PlainTextResponse, Response

from app.api.router import router
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.metrics import increment, normalize_path, observe, render_prometheus
from app.db.enums import ExecutionStatus
from app.db.models import Execution, WorkerHeartbeat
from app.db.session import engine

settings = get_settings()
logger = logging.getLogger("report-manager.api")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API inicial da Plataforma de Relatórios.",
)
app.state.settings = settings


@app.exception_handler(DomainError)
def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "message": error.message, "details": error.details},
        headers={"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None,
    )


@app.exception_handler(RequestValidationError)
def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "invalid_request",
            "message": "Os dados enviados não são válidos.",
            "details": [
                {"location": item.get("loc", []), "message": item.get("msg", "")}
                for item in error.errors()
            ],
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Organization-Id"],
)


@app.middleware("http")
async def correlation_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid4())
    request.state.correlation_id = correlation_id
    started_at = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "organization_id": request.headers.get("X-Organization-Id"),
            },
            ensure_ascii=False,
        )
    )
    labels = {
        "method": request.method,
        "path": normalize_path(request.url.path),
        "status": response.status_code,
    }
    increment("report_manager_http_requests_total", labels=labels)
    observe(
        "report_manager_http_request_duration_seconds",
        time.perf_counter() - started_at,
        labels={"method": request.method, "path": normalize_path(request.url.path)},
    )
    return response


@app.get("/readyz", include_in_schema=False, response_model=None)
def readiness() -> dict[str, object] | JSONResponse:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        worker_last_seen = connection.execute(
            select(func.max(WorkerHeartbeat.last_seen_at)).where(
                WorkerHeartbeat.status == "ATIVO"
            )
        ).scalar_one_or_none()
        queue_depth = connection.execute(
            select(func.count(Execution.id)).where(Execution.status == ExecutionStatus.CREATED)
        ).scalar_one()
    worker_is_ready = bool(
        worker_last_seen
        and (datetime.now(UTC) - worker_last_seen).total_seconds()
        <= settings.worker_readiness_timeout_seconds
    )
    if not worker_is_ready:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "ready",
                "worker": "not_ready",
                "queue_depth": int(queue_depth or 0),
            },
        )
    return {
        "status": "ready",
        "database": "ready",
        "worker": "ready",
        "queue_depth": int(queue_depth or 0),
    }


app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/healthz", include_in_schema=False)
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False, response_class=PlainTextResponse)
def metrics() -> str:
    return render_prometheus()
