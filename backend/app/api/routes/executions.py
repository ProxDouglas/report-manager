from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import RequestContext, require_roles
from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db.enums import AuditResult, ExecutionStatus, Role
from app.db.models import Artifact, Execution, Report, ReportVersion
from app.schemas.execution import (
    ExecutionCreateRequest,
    ExecutionResponse,
    ReadyReportResponse,
)
from app.services.artifact_service import get_downloadable_artifact
from app.services.audit import record_audit
from app.services.execution_service import create_execution
from app.services.report_service import ensure_report_access

router = APIRouter(tags=["executions"])
runner = require_roles(Role.ORGANIZATION_ADMIN, Role.REPORT_CREATOR, Role.VIEWER)


def execution_response(context: RequestContext, execution: Execution) -> ExecutionResponse:
    artifacts = context.db.scalars(
        select(Artifact).where(Artifact.execution_id == execution.id).order_by(Artifact.created_at)
    ).all()
    return ExecutionResponse.model_validate(
        {
            "id": execution.id,
            "report_id": execution.report_id,
            "report_version_id": execution.report_version_id,
            "status": execution.status,
            "parameters": execution.parameters,
            "attempt_count": execution.attempt_count,
            "started_at": execution.started_at,
            "finished_at": execution.finished_at,
            "error_summary": execution.error_summary,
            "created_at": execution.created_at,
            "artifacts": artifacts,
        }
    )


@router.post("/reports/{report_id}/executions", response_model=ExecutionResponse, status_code=202)
def request_execution(
    report_id: UUID,
    payload: ExecutionCreateRequest,
    context: RequestContext = Depends(runner),  # noqa: B008
) -> ExecutionResponse:
    execution = create_execution(
        context.db,
        get_settings(),
        context.organization.id,
        context.user.id,
        context.role,
        report_id,
        payload,
    )
    return execution_response(context, execution)


@router.get("/executions", response_model=list[ExecutionResponse])
def list_executions(context: RequestContext = Depends(runner)) -> list[ExecutionResponse]:  # noqa: B008
    executions = context.db.scalars(
        select(Execution)
        .where(Execution.organization_id == context.organization.id)
        .order_by(Execution.created_at.desc())
        .limit(100)
    ).all()
    visible = []
    for execution in executions:
        report = context.db.get(Report, execution.report_id)
        if report:
            try:
                ensure_report_access(context.db, report, context.user.id, context.role)
                visible.append(execution_response(context, execution))
            except ForbiddenError:
                continue
    return visible


@router.get("/executions/ready", response_model=list[ReadyReportResponse])
def list_ready_reports(context: RequestContext = Depends(runner)) -> list[ReadyReportResponse]:  # noqa: B008
    executions = context.db.scalars(
        select(Execution)
        .where(
            Execution.organization_id == context.organization.id,
            Execution.status == ExecutionStatus.SUCCESS,
        )
        .order_by(Execution.finished_at.desc())
        .limit(100)
    ).all()
    result: list[ReadyReportResponse] = []
    for execution in executions:
        report = context.db.get(Report, execution.report_id)
        if not report:
            continue
        try:
            ensure_report_access(context.db, report, context.user.id, context.role)
        except ForbiddenError:
            continue
        version = context.db.get(ReportVersion, execution.report_version_id)
        if version:
            result.append(
                ReadyReportResponse(
                    execution=execution_response(context, execution),
                    report_name=report.name,
                    version_number=version.version_number,
                )
            )
    return result


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
def get_execution(
    execution_id: UUID, context: RequestContext = Depends(runner)
) -> ExecutionResponse:  # noqa: B008
    execution = context.db.scalar(
        select(Execution).where(
            Execution.id == execution_id, Execution.organization_id == context.organization.id
        )
    )
    if not execution:
        raise NotFoundError("Execução não encontrada.")
    report = context.db.get(Report, execution.report_id)
    if not report:
        raise NotFoundError("Relatório da execução não encontrado.")
    ensure_report_access(context.db, report, context.user.id, context.role)
    return execution_response(context, execution)


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionResponse)
def cancel_execution(
    execution_id: UUID, context: RequestContext = Depends(runner)
) -> ExecutionResponse:  # noqa: B008
    execution = context.db.scalar(
        select(Execution).where(
            Execution.id == execution_id, Execution.organization_id == context.organization.id
        )
    )
    if not execution:
        raise NotFoundError("Execução não encontrada.")
    if execution.status not in {ExecutionStatus.CREATED, ExecutionStatus.RUNNING}:
        raise ConflictError("A execução não pode mais ser cancelada.")
    execution.status = ExecutionStatus.CANCELED
    execution.finished_at = datetime.now(UTC)
    record_audit(
        context.db,
        action="cancel_execution",
        result=AuditResult.SUCCESS,
        organization_id=context.organization.id,
        actor_user_id=context.user.id,
        resource_type="execution",
        resource_id=str(execution.id),
    )
    context.db.commit()
    return execution_response(context, execution)


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: UUID, context: RequestContext = Depends(runner)) -> Response:  # noqa: B008
    artifact = get_downloadable_artifact(context.db, context.organization.id, artifact_id)
    execution = context.db.get(Execution, artifact.execution_id)
    if not execution:
        raise NotFoundError("Execução do artefato não encontrada.")
    report = context.db.get(Report, execution.report_id)
    if report:
        ensure_report_access(context.db, report, context.user.id, context.role)
    record_audit(
        context.db,
        action="download_artifact",
        result=AuditResult.SUCCESS,
        organization_id=context.organization.id,
        actor_user_id=context.user.id,
        resource_type="artifact",
        resource_id=str(artifact.id),
    )
    context.db.commit()
    return Response(
        content=artifact.content,
        media_type=artifact.content_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.file_name}"'},
    )
