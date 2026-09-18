from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db.enums import (
    AuditResult,
    DataClassification,
    GrantTargetType,
    ReportStatus,
    ReportVersionStatus,
    Role,
)
from app.db.models import (
    DataSource,
    Report,
    ReportGrant,
    ReportVersion,
)
from app.services.audit import record_audit
from app.services.source_service import ensure_source_access, latest_version


def ensure_report(db: Session, organization_id: UUID, report_id: UUID) -> Report:
    report = db.scalar(
        select(Report).where(Report.id == report_id, Report.organization_id == organization_id)
    )
    if not report:
        raise NotFoundError("Relatório não encontrado.")
    return report


def ensure_report_access(db: Session, report: Report, user_id: UUID, role: Role | None) -> None:
    if role in {Role.ORGANIZATION_ADMIN, Role.REPORT_CREATOR, Role.PLATFORM_OPERATOR}:
        return
    grant = db.scalar(
        select(ReportGrant).where(
            ReportGrant.report_id == report.id,
            or_(
                (ReportGrant.target_type == "USUARIO") & (ReportGrant.target_id == str(user_id)),
                ReportGrant.target_type == "ORGANIZACAO",
                (ReportGrant.target_type == "PAPEL") & (ReportGrant.target_id == str(role)),
            ),
        )
    )
    if not grant:
        raise ForbiddenError("Usuário não possui acesso a este relatório.")


def validate_definition(
    db: Session,
    organization_id: UUID,
    definition: dict[str, Any],
    user_id: UUID | None = None,
    role: Role | None = None,
) -> None:
    source_ids = definition.get("source_ids") or (
        [definition["source_id"]] if definition.get("source_id") else []
    )
    if not source_ids:
        raise ConflictError("A definição precisa informar ao menos uma fonte.")
    for raw_source_id in source_ids:
        try:
            source_id = UUID(str(raw_source_id))
        except ValueError as exc:
            raise ConflictError("A definição possui uma fonte inválida.") from exc
        source = db.scalar(
            select(DataSource).where(
                DataSource.id == source_id, DataSource.organization_id == organization_id
            )
        )
        if not source:
            raise ForbiddenError("A definição referencia uma fonte de outra organização.")
        if user_id:
            ensure_source_access(db, source, user_id, role, "USE")
        version = latest_version(db, source.id)
        if not version and source.status.value not in {"ATIVA", "RASCUNHO"}:
            raise ConflictError("A fonte referenciada não está disponível.")
        requested_fields = list(definition.get("fields", []))
        requested_fields.extend(definition.get("group_by", []))
        requested_fields.extend(
            item.get("field")
            for item in definition.get("filters", [])
            if isinstance(item, dict)
        )
        requested_fields.extend(
            metric.get("field")
            for metric in definition.get("metrics", [])
            if isinstance(metric, dict)
        )
        if version and requested_fields:
            fields = list(version.schema_snapshot.get("columns", []))
            for catalog_object in version.schema_snapshot.get("objects", []):
                if isinstance(catalog_object, dict):
                    fields.extend(catalog_object.get("columns", []))
            field_names = {
                str(field["name"])
                for field in fields
                if str(field.get("classification")) != DataClassification.SECRET
            }
            missing = {
                str(field) for field in requested_fields if field and str(field) not in field_names
            }
            if missing:
                raise ConflictError(
                    f"Campos não disponíveis no catálogo: {', '.join(sorted(missing))}."
                )


def create_report(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
    name: str,
    objective: str | None,
    definition: dict[str, Any],
    role: Role | None = None,
) -> Report:
    validate_definition(db, organization_id, definition, user_id, role)
    report = Report(
        organization_id=organization_id,
        created_by_user_id=user_id,
        name=name.strip(),
        objective=objective,
        status=ReportStatus.DRAFT,
    )
    db.add(report)
    db.flush()
    version = ReportVersion(
        report_id=report.id,
        version_number=1,
        status=ReportVersionStatus.DRAFT,
        definition=definition,
        created_by_user_id=user_id,
    )
    db.add(version)
    db.flush()
    db.add(
        ReportGrant(
            report_id=report.id,
            target_type="ORGANIZACAO",
            target_id=str(organization_id),
            permission="VIEW",
        )
    )
    record_audit(
        db,
        action="create_report",
        result=AuditResult.SUCCESS,
        organization_id=organization_id,
        actor_user_id=user_id,
        resource_type="report",
        resource_id=str(report.id),
    )
    db.commit()
    db.refresh(report)
    return report


def latest_version_for_report(db: Session, report_id: UUID) -> ReportVersion:
    version = db.scalar(
        select(ReportVersion)
        .where(ReportVersion.report_id == report_id)
        .order_by(ReportVersion.version_number.desc())
    )
    if not version:
        raise NotFoundError("Versão do relatório não encontrada.")
    return version


def create_next_version(
    db: Session,
    report: Report,
    user_id: UUID,
    definition: dict[str, Any],
    summary: str,
    role: Role | None = None,
) -> ReportVersion:
    validate_definition(db, report.organization_id, definition, user_id, role)
    latest = latest_version_for_report(db, report.id)
    version = ReportVersion(
        report_id=report.id,
        version_number=latest.version_number + 1,
        status=ReportVersionStatus.DRAFT,
        definition=definition,
        change_summary=summary,
        created_by_user_id=user_id,
    )
    db.add(version)
    report.status = ReportStatus.DRAFT
    db.commit()
    db.refresh(version)
    record_audit(
        db,
        action="create_report_version",
        result=AuditResult.SUCCESS,
        organization_id=report.organization_id,
        actor_user_id=user_id,
        resource_type="report_version",
        resource_id=str(version.id),
        details={"version_number": version.version_number, "summary": summary},
    )
    db.commit()
    return version


def publish_version(
    db: Session,
    report: Report,
    version: ReportVersion,
    user_id: UUID,
    role: Role | None = None,
) -> ReportVersion:
    validate_definition(db, report.organization_id, version.definition, user_id, role)
    if version.status is ReportVersionStatus.PUBLISHED:
        return version
    published = db.scalars(
        select(ReportVersion).where(
            ReportVersion.report_id == report.id,
            ReportVersion.status == ReportVersionStatus.PUBLISHED,
        )
    ).all()
    for old_version in published:
        old_version.status = ReportVersionStatus.ARCHIVED
    version.status = ReportVersionStatus.PUBLISHED
    version.published_at = datetime.now(UTC)
    report.status = ReportStatus.PUBLISHED
    report.published_version_id = version.id
    record_audit(
        db,
        action="publish_report_version",
        result=AuditResult.SUCCESS,
        organization_id=report.organization_id,
        actor_user_id=user_id,
        resource_type="report_version",
        resource_id=str(version.id),
        details={"version_number": version.version_number},
    )
    db.commit()
    db.refresh(version)
    return version


def resolve_published_version(db: Session, report: Report) -> ReportVersion:
    if not report.published_version_id:
        raise ConflictError("O relatório não possui versão publicada.")
    version = db.get(ReportVersion, report.published_version_id)
    if not version or version.status is not ReportVersionStatus.PUBLISHED:
        raise ConflictError("A versão publicada do relatório não está disponível.")
    return version


def create_report_grant(
    db: Session,
    report: Report,
    user_id: UUID,
    target_type: GrantTargetType,
    target_id: str,
    permission: str,
) -> ReportGrant:
    normalized_target = target_id.strip()
    if target_type is GrantTargetType.ORGANIZATION:
        if normalized_target != str(report.organization_id):
            raise ForbiddenError("O grant deve apontar para a própria organização.")
    elif target_type is GrantTargetType.USER:
        from app.db.models import Membership

        try:
            target_user_id = UUID(normalized_target)
        except ValueError as exc:
            raise ConflictError("O usuário do grant é inválido.") from exc
        member = db.scalar(
            select(Membership).where(
                Membership.organization_id == report.organization_id,
                Membership.user_id == target_user_id,
                Membership.is_active.is_(True),
            )
        )
        if not member:
            raise ForbiddenError("O usuário do grant não pertence à organização.")
    elif target_type is GrantTargetType.ROLE:
        try:
            role = Role(normalized_target)
        except ValueError as exc:
            raise ConflictError("Papel inválido para o grant.") from exc
        if role is Role.PLATFORM_OPERATOR:
            raise ForbiddenError("O papel de operador não pode ser concedido no cliente.")
    else:
        raise ConflictError("Tipo de alvo do grant não suportado.")
    existing = db.scalar(
        select(ReportGrant).where(
            ReportGrant.report_id == report.id,
            ReportGrant.target_type == target_type,
            ReportGrant.target_id == normalized_target,
        )
    )
    if existing:
        existing.permission = permission
        grant = existing
    else:
        grant = ReportGrant(
            report_id=report.id,
            target_type=target_type,
            target_id=normalized_target,
            permission=permission,
        )
        db.add(grant)
    record_audit(
        db,
        action="create_report_grant",
        result=AuditResult.SUCCESS,
        organization_id=report.organization_id,
        actor_user_id=user_id,
        resource_type="report_grant",
        details={"target_type": target_type, "permission": permission},
    )
    db.commit()
    db.refresh(grant)
    return grant
