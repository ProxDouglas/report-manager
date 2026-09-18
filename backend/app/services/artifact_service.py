from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError, NotFoundError
from app.core.metrics import increment
from app.db.enums import ArtifactType, ExecutionStatus
from app.db.models import Artifact, Execution
from app.services.storage import get_artifact_store


def add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def store_artifact(
    db: Session,
    settings: Settings,
    *,
    organization_id: UUID,
    execution_id: UUID,
    report_version_id: UUID,
    artifact_type: ArtifactType,
    file_name: str,
    content_type: str,
    content: bytes,
) -> Artifact:
    if len(content) > settings.artifact_max_bytes:
        raise DomainError(
            "O artefato excede o tamanho máximo configurado.", "artifact_limit_exceeded", 413
        )
    now = datetime.now(UTC)
    store = get_artifact_store(settings)
    artifact = Artifact(
        organization_id=organization_id,
        execution_id=execution_id,
        report_version_id=report_version_id,
        artifact_type=artifact_type,
        storage_key=store.create_storage_key(),
        file_name=file_name,
        content_type=content_type,
        content=content,
        checksum=store.checksum(content),
        size_bytes=len(content),
        expires_at=add_years(now, settings.retention_artifacts_years),
    )
    db.add(artifact)
    db.flush()
    increment("report_manager_artifact_bytes_total", len(content))
    return artifact


def get_downloadable_artifact(db: Session, organization_id: UUID, artifact_id: UUID) -> Artifact:
    artifact = db.scalar(
        select(Artifact)
        .join(Execution, Execution.id == Artifact.execution_id)
        .where(
            Artifact.id == artifact_id,
            Artifact.organization_id == organization_id,
            Execution.status == ExecutionStatus.SUCCESS,
        )
    )
    if not artifact:
        raise NotFoundError("Artefato não encontrado.")
    if artifact.expires_at <= datetime.now(UTC) or artifact.content is None:
        raise NotFoundError("O artefato expirou ou não está disponível.")
    return artifact
