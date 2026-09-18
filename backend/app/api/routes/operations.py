from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import RequestContext, require_roles
from app.core.config import Settings, get_settings
from app.db.enums import ExecutionStatus, OutboxStatus, Role
from app.db.models import (
    Artifact,
    DataSource,
    DataSourceVersion,
    Execution,
    License,
    OutboxEvent,
    WorkerHeartbeat,
)

router = APIRouter(prefix="/operations", tags=["operations"])
admin = require_roles(Role.ORGANIZATION_ADMIN)


@router.get("/storage")
def storage_report(
    context: RequestContext = Depends(admin),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, object]:
    artifact_count, artifact_bytes = context.db.execute(
        select(
            func.count(Artifact.id),
            func.coalesce(func.sum(Artifact.size_bytes), 0),
        ).where(Artifact.organization_id == context.organization.id)
    ).one()
    source_count, source_bytes = context.db.execute(
        select(
            func.count(DataSourceVersion.id),
            func.coalesce(func.sum(func.length(DataSourceVersion.content)), 0),
        )
        .join(DataSource, DataSource.id == DataSourceVersion.data_source_id)
        .where(DataSource.organization_id == context.organization.id)
    ).one()
    return {
        "artifact_count": int(artifact_count or 0),
        "artifact_bytes": int(artifact_bytes or 0),
        "source_snapshot_count": int(source_count or 0),
        "source_snapshot_bytes": int(source_bytes or 0),
        "retention_years": settings.retention_artifacts_years,
    }


@router.get("/alerts")
def operational_alerts(
    context: RequestContext = Depends(admin),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, object]:
    now = datetime.now(UTC)
    alerts: list[dict[str, object]] = []
    heartbeat = context.db.scalar(
        select(WorkerHeartbeat)
        .order_by(WorkerHeartbeat.last_seen_at.desc())
        .limit(1)
    )
    worker_is_stale = not heartbeat or (
        now - heartbeat.last_seen_at
    ).total_seconds() > settings.worker_readiness_timeout_seconds
    if worker_is_stale:
        alerts.append(
            {
                "code": "worker_not_ready",
                "severity": "critical",
                "message": "Nenhum worker confirmou atividade dentro da janela esperada.",
            }
        )

    stalled_queue = context.db.scalar(
        select(func.count(Execution.id)).where(
            Execution.organization_id == context.organization.id,
            Execution.status == ExecutionStatus.CREATED,
            Execution.created_at <= now - timedelta(seconds=settings.queue_stall_seconds),
        )
    )
    if stalled_queue:
        alerts.append(
            {
                "code": "queue_stalled",
                "severity": "critical",
                "message": "Há execuções aguardando na fila além do limite configurado.",
                "count": int(stalled_queue),
            }
        )

    artifact_bytes = context.db.scalar(
        select(func.coalesce(func.sum(Artifact.size_bytes), 0)).where(
            Artifact.organization_id == context.organization.id,
            Artifact.content.is_not(None),
        )
    )
    if int(artifact_bytes or 0) >= settings.artifact_storage_warning_bytes:
        alerts.append(
            {
                "code": "artifact_storage_high",
                "severity": "warning",
                "message": "O volume de artefatos no PostgreSQL atingiu o limite de alerta.",
                "bytes": int(artifact_bytes or 0),
            }
        )

    license_record = context.license or context.db.scalar(
        select(License).where(License.organization_id == context.organization.id)
    )
    if license_record and license_record.ends_on:
        days_until_expiration = (license_record.ends_on - date.today()).days
        if 0 <= days_until_expiration <= settings.license_expiration_warning_days:
            alerts.append(
                {
                    "code": "license_expiring",
                    "severity": "warning",
                    "message": "A licença da organização está próxima do vencimento.",
                    "days": days_until_expiration,
                }
            )

    smtp_failures = context.db.scalar(
        select(func.count(OutboxEvent.id)).where(
            OutboxEvent.organization_id == context.organization.id,
            OutboxEvent.status == OutboxStatus.FAILED,
            OutboxEvent.created_at >= now - timedelta(days=1),
            OutboxEvent.event_type == "distribution.email",
        )
    )
    if smtp_failures:
        alerts.append(
            {
                "code": "smtp_failures",
                "severity": "warning",
                "message": "Houve falhas de SMTP nas últimas 24 horas.",
                "count": int(smtp_failures),
            }
        )
    return {"generated_at": now, "alerts": alerts}
