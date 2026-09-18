from __future__ import annotations

import time
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.metrics import increment, observe
from app.core.secrets import get_secret_manager
from app.db.enums import ArtifactType, AuditResult, ExecutionStatus, LicenseStatus, Role, SourceType
from app.db.models import (
    Artifact,
    Execution,
    ExecutionAttempt,
    ExecutionSourceVersion,
    License,
    Membership,
    Report,
    ReportVersion,
    User,
    utc_now,
)
from app.schemas.execution import ExecutionCreateRequest
from app.services.analysis import analyze_rows, protect_rows
from app.services.artifact_service import store_artifact
from app.services.audit import record_audit
from app.services.connectors import RelationalConnector
from app.services.rendering import render_chart, render_csv, render_pdf, render_screen, render_xlsx
from app.services.report_service import ensure_report_access, resolve_published_version
from app.services.sandbox import DockerSandboxExecutor
from app.services.source_parser import parse_file
from app.services.source_service import ensure_source, ensure_source_access, latest_version


def _definition_source_id(definition: dict[str, Any]) -> UUID:
    raw = definition.get("source_id") or (definition.get("source_ids") or [None])[0]
    if not raw:
        raise ConflictError("A definição precisa informar uma fonte.")
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise ConflictError("A definição informa uma fonte inválida.") from exc


def create_execution(
    db: Session,
    settings: Settings,
    organization_id: UUID,
    user_id: UUID,
    role: Any,
    report_id: UUID,
    payload: ExecutionCreateRequest,
) -> Execution:
    report = db.scalar(
        select(Report).where(Report.id == report_id, Report.organization_id == organization_id)
    )
    if not report:
        raise NotFoundError("Relatório não encontrado.")
    ensure_report_access(db, report, user_id, role)
    version = resolve_published_version(db, report)
    key = payload.idempotency_key or str(uuid4())
    existing = db.scalar(
        select(Execution).where(
            Execution.organization_id == organization_id, Execution.idempotency_key == key
        )
    )
    if existing:
        return existing
    running_count = db.scalar(
        select(func.count(Execution.id))
        .where(
            Execution.organization_id == organization_id,
            Execution.status.in_([ExecutionStatus.CREATED, ExecutionStatus.RUNNING]),
        )
    )
    if (
        running_count is not None
        and running_count >= settings.max_concurrent_executions_per_organization
    ):
        raise ConflictError("A organização atingiu o limite de execuções simultâneas.")
    source = ensure_source(db, organization_id, _definition_source_id(version.definition))
    ensure_source_access(db, source, user_id, role, "USE")
    if source.status.value in {"PAUSADA", "REVOGADA", "ERRO"}:
        raise ConflictError("A fonte do relatório não está disponível para execução.")
    execution = Execution(
        organization_id=organization_id,
        report_id=report.id,
        report_version_id=version.id,
        requested_by_user_id=user_id,
        status=ExecutionStatus.CREATED,
        parameters=payload.parameters,
        idempotency_key=key,
    )
    db.add(execution)
    record_audit(
        db,
        action="create_execution",
        result=AuditResult.SUCCESS,
        organization_id=organization_id,
        actor_user_id=user_id,
        resource_type="execution",
        details={"report_id": str(report.id), "version_id": str(version.id)},
    )
    db.commit()
    db.refresh(execution)
    return execution


def claim_next_execution(db: Session) -> Execution | None:
    execution = db.scalar(
        select(Execution)
        .where(Execution.status == ExecutionStatus.CREATED)
        .order_by(Execution.created_at)
        .with_for_update(skip_locked=True)
    )
    if not execution:
        return None
    now = utc_now()
    execution.status = ExecutionStatus.RUNNING
    execution.started_at = now
    execution.attempt_count += 1
    attempt = ExecutionAttempt(
        execution_id=execution.id,
        attempt_number=execution.attempt_count,
        status=ExecutionStatus.RUNNING,
        started_at=now,
    )
    db.add(attempt)
    db.commit()
    db.refresh(execution)
    return execution


def _check_timeout(started_at: float, settings: Settings) -> None:
    if time.monotonic() - started_at > settings.execution_timeout_seconds:
        raise DomainError("A execução excedeu o tempo máximo.", "execution_timeout", 408)


def _check_cancellation(db: Session, execution_id: UUID) -> None:
    status = db.scalar(select(Execution.status).where(Execution.id == execution_id))
    if status is ExecutionStatus.CANCELED:
        raise DomainError("A execução foi cancelada.", "execution_canceled", 409)


def _collect_rows(
    db: Session,
    settings: Settings,
    execution: Execution,
    version: ReportVersion,
) -> list[dict[str, Any]]:
    definition = version.definition
    source_id = _definition_source_id(definition)
    source = ensure_source(db, execution.organization_id, source_id)
    requested_role = db.scalar(
        select(Membership.role).where(
            Membership.organization_id == execution.organization_id,
            Membership.user_id == execution.requested_by_user_id,
            Membership.is_active.is_(True),
        )
    )
    is_platform_operator = db.scalar(
        select(User.is_platform_operator).where(User.id == execution.requested_by_user_id)
    )
    if is_platform_operator:
        requested_role = Role.PLATFORM_OPERATOR
    ensure_source_access(
        db,
        source,
        execution.requested_by_user_id,
        requested_role,
        "USE",
    )
    source_version = latest_version(db, source.id)
    if source.source_type in {SourceType.CSV, SourceType.EXCEL, SourceType.JSON}:
        if not source_version or not source_version.content:
            raise ConflictError("A fonte não possui snapshot válido.")
        rows, schema = parse_file(
            source.source_type,
            source_version.content,
            source_version.import_config,
            min(settings.execution_max_rows, settings.source_max_sheet_rows),
            settings.source_max_columns,
            settings.source_max_json_depth,
        )
        db.add(
            ExecutionSourceVersion(
                execution_id=execution.id,
                source_id=source.id,
                source_version_id=source_version.id,
                schema_snapshot=schema,
            )
        )
    else:
        query = str(definition.get("query", ""))
        connector = RelationalConnector(
            get_secret_manager(settings),
            settings.source_connection_timeout_seconds,
            settings.public_source_ips_only,
        )
        rows = connector.read_rows(
            source, query, dict(definition.get("query_parameters", {})), settings.execution_max_rows
        )
        schema = {
            "columns": [
                {"name": key, "type": type(value).__name__}
                for key, value in (rows[0].items() if rows else [])
            ]
        }
        db.add(
            ExecutionSourceVersion(
                execution_id=execution.id, source_id=source.id, schema_snapshot=schema
            )
        )
    return rows


def execute_one(db: Session, settings: Settings, execution: Execution) -> None:
    start = time.monotonic()
    version = db.get(ReportVersion, execution.report_version_id)
    if not version:
        raise ConflictError("A versão da execução não está disponível.")
    license_record = db.scalar(
        select(License).where(License.organization_id == execution.organization_id)
    )
    today = date.today()
    license_is_current = bool(
        license_record
        and license_record.status is LicenseStatus.ACTIVE
        and license_record.starts_on <= today
        and (license_record.ends_on is None or license_record.ends_on >= today)
    )
    if not license_is_current:
        raise ConflictError("A licença não está ativa para executar o relatório.")
    rows = _collect_rows(db, settings, execution, version)
    _check_cancellation(db, execution.id)
    _check_timeout(start, settings)
    definition = version.definition
    if definition.get("python_code"):
        rows = DockerSandboxExecutor(settings).execute(str(definition["python_code"]), rows)
    _check_cancellation(db, execution.id)
    analyzed = analyze_rows(rows, definition, settings.execution_max_rows)
    protected = protect_rows(analyzed)
    outputs = definition.get("formats") or ["TELA", "CSV", "XLSX", "PDF"]
    total_size = 0
    artifacts: list[tuple[ArtifactType, str, str, bytes]] = []
    report = db.get(Report, execution.report_id)
    title = report.name if report else "Relatório"
    for raw_format in outputs:
        format_name = str(raw_format).upper()
        if format_name in {"TELA", "SCREEN"}:
            artifacts.append(
                (
                    ArtifactType.SCREEN,
                    "resultado.json",
                    "application/json",
                    render_screen(protected),
                )
            )
        elif format_name == "CSV":
            artifacts.append((ArtifactType.CSV, "resultado.csv", "text/csv", render_csv(protected)))
        elif format_name == "XLSX":
            artifacts.append(
                (
                    ArtifactType.XLSX,
                    "resultado.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    render_xlsx(protected),
                )
            )
        elif format_name == "PDF":
            artifacts.append(
                (
                    ArtifactType.PDF,
                    "resultado.pdf",
                    "application/pdf",
                    render_pdf(title, version.version_number, protected),
                )
            )
        else:
            raise ConflictError(f"Formato de saída não suportado: {format_name}.")
    chart_configuration = definition.get("chart")
    if (
        isinstance(chart_configuration, dict)
        and chart_configuration.get("x")
        and chart_configuration.get("y")
    ):
        artifacts.append(
            (
                ArtifactType.CHART,
                "grafico.png",
                "image/png",
                render_chart(protected, chart_configuration),
            )
        )
    for artifact_type, file_name, content_type, content in artifacts:
        total_size += len(content)
        if total_size > settings.execution_max_result_bytes:
            raise DomainError(
                "O resultado excede o tamanho máximo permitido.", "execution_result_limit", 413
            )
        store_artifact(
            db,
            settings,
            organization_id=execution.organization_id,
            execution_id=execution.id,
            report_version_id=version.id,
            artifact_type=artifact_type,
            file_name=file_name,
            content_type=content_type,
            content=content,
        )
        _check_cancellation(db, execution.id)
        _check_timeout(start, settings)
    execution.status = ExecutionStatus.SUCCESS
    execution.finished_at = utc_now()
    attempt = db.scalar(
        select(ExecutionAttempt).where(
            ExecutionAttempt.execution_id == execution.id,
            ExecutionAttempt.attempt_number == execution.attempt_count,
        )
    )
    if attempt:
        attempt.status = ExecutionStatus.SUCCESS
        attempt.finished_at = utc_now()
    record_audit(
        db,
        action="complete_execution",
        result=AuditResult.SUCCESS,
        organization_id=execution.organization_id,
        actor_user_id=execution.requested_by_user_id,
        resource_type="execution",
        resource_id=str(execution.id),
        details={"report_version_id": str(version.id)},
    )
    db.commit()
    increment("report_manager_executions_total", labels={"status": "success"})
    observe(
        "report_manager_execution_duration_seconds",
        time.monotonic() - start,
        labels={"status": "success"},
    )


def run_claimed_execution(db: Session, settings: Settings, execution: Execution) -> None:
    try:
        execute_one(db, settings, execution)
    except Exception as exc:
        db.rollback()
        attempt = db.get(Execution, execution.id)
        if not attempt:
            return
        for artifact in db.scalars(
            select(Artifact).where(Artifact.execution_id == attempt.id)
        ).all():
            artifact.content = None
        if attempt.status is ExecutionStatus.CANCELED:
            canceled_attempt = db.scalar(
                select(ExecutionAttempt).where(
                    ExecutionAttempt.execution_id == attempt.id,
                    ExecutionAttempt.attempt_number == attempt.attempt_count,
                )
            )
            if canceled_attempt:
                canceled_attempt.status = ExecutionStatus.CANCELED
                canceled_attempt.finished_at = utc_now()
            db.commit()
            increment("report_manager_executions_total", labels={"status": "canceled"})
            return
        attempt.status = ExecutionStatus.FAILED
        attempt.error_summary = (
            exc.message if isinstance(exc, DomainError) else "Falha interna na execução."
        )
        current_attempt = db.scalar(
            select(ExecutionAttempt).where(
                ExecutionAttempt.execution_id == attempt.id,
                ExecutionAttempt.attempt_number == attempt.attempt_count,
            )
        )
        if current_attempt:
            current_attempt.status = ExecutionStatus.FAILED
            current_attempt.finished_at = utc_now()
            current_attempt.error_summary = attempt.error_summary
        if attempt.attempt_count < settings.sandbox_max_retries:
            attempt.status = ExecutionStatus.CREATED
            increment("report_manager_execution_retries_total")
        else:
            attempt.status = ExecutionStatus.FAILED
            attempt.finished_at = utc_now()
        record_audit(
            db,
            action="fail_execution",
            result=AuditResult.FAILURE,
            organization_id=attempt.organization_id,
            actor_user_id=attempt.requested_by_user_id,
            resource_type="execution",
            resource_id=str(attempt.id),
            details={"error": attempt.error_summary, "attempt": attempt.attempt_count},
        )
        db.commit()
        increment("report_manager_executions_total", labels={"status": "failed"})
