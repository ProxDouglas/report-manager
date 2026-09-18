from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.enums import AuditResult
from app.db.models import (
    Artifact,
    AuditEvent,
    DataSource,
    DataSourceVersion,
    ExecutionAttempt,
)
from app.services.artifact_service import add_years
from app.services.audit import record_audit


def run_retention(db: Session, settings: Settings) -> dict[str, int]:
    now = datetime.now(UTC)
    artifacts = db.scalars(
        select(Artifact).where(Artifact.expires_at <= now, Artifact.content.is_not(None))
    ).all()
    for artifact in artifacts:
        artifact.content = None
    cutoff = add_years(now, -settings.retention_source_snapshots_years)
    source_versions = db.scalars(
        select(DataSourceVersion).where(
            DataSourceVersion.created_at <= cutoff,
            DataSourceVersion.content.is_not(None),
            DataSourceVersion.is_latest_valid.is_(False),
        )
    ).all()
    source_ids = {version.data_source_id for version in source_versions}
    for version in source_versions:
        version.content = None
    affected_organizations = {artifact.organization_id for artifact in artifacts}
    if source_ids:
        affected_organizations.update(
            db.scalars(
                select(DataSource.organization_id).where(DataSource.id.in_(source_ids))
            ).all()
        )
    execution_cutoff = add_years(now, -settings.retention_execution_logs_years)
    old_attempts = db.scalars(
        select(ExecutionAttempt).where(
            ExecutionAttempt.finished_at.is_not(None),
            ExecutionAttempt.finished_at <= execution_cutoff,
            ExecutionAttempt.diagnostics != {},
        )
    ).all()
    for attempt in old_attempts:
        attempt.diagnostics = {}
        attempt.error_summary = None

    audit_cutoff = add_years(now, -settings.retention_audit_logs_years)
    old_audits = db.scalars(
        select(AuditEvent).where(
            AuditEvent.created_at <= audit_cutoff,
            AuditEvent.details != {},
        )
    ).all()
    for event in old_audits:
        event.details = {}
    for organization_id in affected_organizations:
        record_audit(
            db,
            action="retention_cleanup",
            result=AuditResult.SUCCESS,
            organization_id=organization_id,
            resource_type="retention",
            details={
                "artifacts_cleaned": len(artifacts),
                "source_snapshots_cleaned": len(source_versions),
                "execution_logs_minimized": len(old_attempts),
                "audit_payloads_minimized": len(old_audits),
            },
        )
    db.commit()
    return {
        "artifacts_cleaned": len(artifacts),
        "source_snapshots_cleaned": len(source_versions),
        "execution_logs_minimized": len(old_attempts),
        "audit_payloads_minimized": len(old_audits),
    }
