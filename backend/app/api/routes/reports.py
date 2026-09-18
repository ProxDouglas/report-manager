from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import RequestContext, require_roles
from app.core.errors import ForbiddenError, NotFoundError
from app.db.enums import Role
from app.db.models import Report, ReportGrant, ReportVersion
from app.schemas.report import (
    ReportCreateRequest,
    ReportGrantCreateRequest,
    ReportGrantResponse,
    ReportResponse,
    ReportUpdateRequest,
    ReportVersionResponse,
)
from app.services.report_service import (
    create_next_version,
    create_report,
    create_report_grant,
    ensure_report,
    ensure_report_access,
    latest_version_for_report,
    publish_version,
)

router = APIRouter(prefix="/reports", tags=["reports"])
writer = require_roles(Role.ORGANIZATION_ADMIN, Role.REPORT_CREATOR)
reader = require_roles(Role.ORGANIZATION_ADMIN, Role.REPORT_CREATOR, Role.VIEWER)


@router.get("", response_model=list[ReportResponse])
def list_reports(context: RequestContext = Depends(reader)) -> list[ReportResponse]:  # noqa: B008
    reports = context.db.scalars(
        select(Report)
        .where(Report.organization_id == context.organization.id)
        .order_by(Report.updated_at.desc())
    ).all()
    visible: list[Report] = []
    for report in reports:
        try:
            ensure_report_access(context.db, report, context.user.id, context.role)
            visible.append(report)
        except ForbiddenError:
            continue
    return [ReportResponse.model_validate(report) for report in visible]


@router.post("", response_model=ReportResponse, status_code=201)
def create_report_endpoint(
    payload: ReportCreateRequest,
    context: RequestContext = Depends(writer),  # noqa: B008
) -> ReportResponse:
    report = create_report(
        context.db,
        context.organization.id,
        context.user.id,
        payload.name,
        payload.objective,
        payload.definition,
        context.role,
    )
    return ReportResponse.model_validate(report)


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: UUID, context: RequestContext = Depends(reader)) -> ReportResponse:  # noqa: B008
    report = ensure_report(context.db, context.organization.id, report_id)
    ensure_report_access(context.db, report, context.user.id, context.role)
    return ReportResponse.model_validate(report)


@router.get("/{report_id}/versions", response_model=list[ReportVersionResponse])
def list_versions(
    report_id: UUID, context: RequestContext = Depends(reader)
) -> list[ReportVersionResponse]:  # noqa: B008
    report = ensure_report(context.db, context.organization.id, report_id)
    ensure_report_access(context.db, report, context.user.id, context.role)
    versions = context.db.scalars(
        select(ReportVersion)
        .where(ReportVersion.report_id == report.id)
        .order_by(ReportVersion.version_number.desc())
    ).all()
    return [ReportVersionResponse.model_validate(version) for version in versions]


@router.post("/{report_id}/versions", response_model=ReportVersionResponse, status_code=201)
def create_version(
    report_id: UUID,
    payload: ReportUpdateRequest,
    context: RequestContext = Depends(writer),  # noqa: B008
) -> ReportVersionResponse:
    report = ensure_report(context.db, context.organization.id, report_id)
    version = create_next_version(
        context.db,
        report,
        context.user.id,
        payload.definition,
        payload.change_summary,
        context.role,
    )
    return ReportVersionResponse.model_validate(version)


@router.post("/{report_id}/versions/{version_id}/publish", response_model=ReportVersionResponse)
def publish_report_version(
    report_id: UUID,
    version_id: UUID,
    context: RequestContext = Depends(writer),  # noqa: B008
) -> ReportVersionResponse:
    report = ensure_report(context.db, context.organization.id, report_id)
    version = context.db.scalar(
        select(ReportVersion).where(
            ReportVersion.id == version_id, ReportVersion.report_id == report.id
        )
    )
    if not version:
        raise NotFoundError("Versão do relatório não encontrada.")
    published = publish_version(context.db, report, version, context.user.id, context.role)
    return ReportVersionResponse.model_validate(published)


@router.post("/{report_id}/duplicate", response_model=ReportVersionResponse, status_code=201)
def duplicate_report_version(
    report_id: UUID,
    context: RequestContext = Depends(writer),  # noqa: B008
) -> ReportVersionResponse:
    report = ensure_report(context.db, context.organization.id, report_id)
    version = latest_version_for_report(context.db, report.id)
    duplicated = create_next_version(
        context.db,
        report,
        context.user.id,
        dict(version.definition),
        "Duplicação da versão anterior.",
        context.role,
    )
    return ReportVersionResponse.model_validate(duplicated)


@router.get("/{report_id}/grants", response_model=list[ReportGrantResponse])
def list_report_grants(
    report_id: UUID, context: RequestContext = Depends(writer)
) -> list[ReportGrantResponse]:  # noqa: B008
    report = ensure_report(context.db, context.organization.id, report_id)
    grants = context.db.scalars(
        select(ReportGrant)
        .where(ReportGrant.report_id == report.id)
        .order_by(ReportGrant.created_at)
    ).all()
    return [ReportGrantResponse.model_validate(grant) for grant in grants]


@router.get("/{report_id}/versions/{version_id}/diff")
def report_version_diff(
    report_id: UUID,
    version_id: UUID,
    compare_to_version_id: UUID | None = None,
    context: RequestContext = Depends(reader),  # noqa: B008
) -> dict[str, object]:
    report = ensure_report(context.db, context.organization.id, report_id)
    ensure_report_access(context.db, report, context.user.id, context.role)
    current = context.db.scalar(
        select(ReportVersion).where(
            ReportVersion.id == version_id,
            ReportVersion.report_id == report.id,
        )
    )
    if not current:
        raise NotFoundError("Versão do relatório não encontrada.")
    previous = None
    if compare_to_version_id:
        previous = context.db.scalar(
            select(ReportVersion).where(
                ReportVersion.id == compare_to_version_id,
                ReportVersion.report_id == report.id,
            )
        )
    if previous is None:
        previous = context.db.scalar(
            select(ReportVersion)
            .where(
                ReportVersion.report_id == report.id,
                ReportVersion.version_number < current.version_number,
            )
            .order_by(ReportVersion.version_number.desc())
        )
    previous_definition = previous.definition if previous else {}
    changed = sorted(
        key
        for key in set(current.definition) | set(previous_definition)
        if current.definition.get(key) != previous_definition.get(key)
    )
    return {
        "report_id": report.id,
        "version_id": current.id,
        "compare_to_version_id": previous.id if previous else None,
        "changed_keys": changed,
        "current": current.definition,
        "previous": previous_definition,
    }


@router.post("/{report_id}/grants", response_model=ReportGrantResponse, status_code=201)
def add_report_grant(
    report_id: UUID,
    payload: ReportGrantCreateRequest,
    context: RequestContext = Depends(require_roles(Role.ORGANIZATION_ADMIN)),  # noqa: B008
) -> ReportGrantResponse:
    report = ensure_report(context.db, context.organization.id, report_id)
    grant = create_report_grant(
        context.db,
        report,
        context.user.id,
        payload.target_type,
        payload.target_id,
        payload.permission,
    )
    return ReportGrantResponse.model_validate(grant)


@router.delete("/{report_id}/grants/{grant_id}")
def delete_report_grant(
    report_id: UUID,
    grant_id: UUID,
    context: RequestContext = Depends(require_roles(Role.ORGANIZATION_ADMIN)),  # noqa: B008
) -> dict[str, object]:
    report = ensure_report(context.db, context.organization.id, report_id)
    grant = context.db.scalar(
        select(ReportGrant).where(ReportGrant.id == grant_id, ReportGrant.report_id == report.id)
    )
    if not grant:
        raise NotFoundError("Grant não encontrado.")
    context.db.delete(grant)
    context.db.commit()
    return {"deleted": True, "id": grant_id}
