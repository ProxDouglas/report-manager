from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.enums import (
    ArtifactType,
    ExecutionStatus,
    LicenseStatus,
    OrganizationStatus,
    ReportStatus,
    ReportVersionStatus,
    Role,
    SourceStatus,
    SourceType,
    SourceVersionStatus,
)
from app.db.models import (
    Artifact,
    DataSource,
    DataSourceVersion,
    License,
    Organization,
    Report,
    ReportVersion,
    User,
)
from app.schemas.execution import ExecutionCreateRequest
from app.services.execution_service import (
    _check_timeout,
    claim_next_execution,
    create_execution,
    run_claimed_execution,
)


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite://",
        sandbox_max_retries=1,
        execution_max_rows=100,
        execution_max_result_bytes=1_000_000,
    )


def _create_report(database: Session, formats: list[str] | None = None) -> tuple[User, Report]:
    organization = Organization(
        name="Pipeline", slug="pipeline", status=OrganizationStatus.ACTIVE
    )
    user = User(
        email="pipeline@example.com",
        display_name="Pipeline",
        password_hash="hash",
        must_change_password=False,
    )
    database.add_all([organization, user])
    database.flush()
    database.add(
        License(
            organization_id=organization.id,
            status=LicenseStatus.ACTIVE,
            starts_on=date.today(),
        )
    )
    source = DataSource(
        organization_id=organization.id,
        owner_user_id=user.id,
        name="CSV",
        source_type=SourceType.CSV,
        status=SourceStatus.ACTIVE,
    )
    database.add(source)
    database.flush()
    database.add(
        DataSourceVersion(
            data_source_id=source.id,
            version_number=1,
            status=SourceVersionStatus.VALID,
            is_latest_valid=True,
            content=b"category,value\nA,2\nA,3\n",
            schema_snapshot={
                "columns": [
                    {"name": "category", "type": "string"},
                    {"name": "value", "type": "integer"},
                ]
            },
            created_by_user_id=user.id,
        )
    )
    database.flush()
    report = Report(
        organization_id=organization.id,
        created_by_user_id=user.id,
        name="Resumo",
        objective="Teste",
        status=ReportStatus.PUBLISHED,
    )
    database.add(report)
    database.flush()
    version = ReportVersion(
        report_id=report.id,
        version_number=1,
        status=ReportVersionStatus.PUBLISHED,
        definition={
            "source_id": str(source.id),
            "fields": ["category", "value"],
            "metrics": [{"name": "total", "field": "value", "operation": "sum"}],
            "group_by": ["category"],
            "formats": formats or ["TELA", "CSV"],
        },
        created_by_user_id=user.id,
    )
    database.add(version)
    database.flush()
    report.published_version_id = version.id
    database.commit()
    return user, report


def test_execution_is_idempotent_and_produces_artifacts(database: Session) -> None:
    user, report = _create_report(database)
    settings = _settings()
    payload = ExecutionCreateRequest(idempotency_key="same-request")
    first = create_execution(
        database,
        settings,
        report.organization_id,
        user.id,
        Role.ORGANIZATION_ADMIN,
        report.id,
        payload,
    )
    second = create_execution(
        database,
        settings,
        report.organization_id,
        user.id,
        Role.ORGANIZATION_ADMIN,
        report.id,
        payload,
    )
    assert first.id == second.id
    claimed = claim_next_execution(database)
    assert claimed is not None
    run_claimed_execution(database, settings, claimed)
    database.refresh(claimed)
    assert claimed.status is ExecutionStatus.SUCCESS
    artifacts = database.scalars(
        select(Artifact).where(Artifact.execution_id == claimed.id)
    ).all()
    assert {artifact.artifact_type for artifact in artifacts} == {
        ArtifactType.SCREEN,
        ArtifactType.CSV,
    }


def test_execution_failure_is_persisted_without_exposing_exception(database: Session) -> None:
    user, report = _create_report(database, ["UNSUPPORTED"])
    settings = _settings()
    execution = create_execution(
        database,
        settings,
        report.organization_id,
        user.id,
        Role.ORGANIZATION_ADMIN,
        report.id,
        ExecutionCreateRequest(),
    )
    claimed = claim_next_execution(database)
    assert claimed is not None
    run_claimed_execution(database, settings, claimed)
    database.refresh(execution)
    assert execution.status is ExecutionStatus.FAILED
    assert execution.error_summary == "Formato de saída não suportado: UNSUPPORTED."


def test_execution_retries_once_then_fails(database: Session) -> None:
    user, report = _create_report(database, ["UNSUPPORTED"])
    settings = _settings().model_copy(update={"sandbox_max_retries": 2})
    execution = create_execution(
        database,
        settings,
        report.organization_id,
        user.id,
        Role.ORGANIZATION_ADMIN,
        report.id,
        ExecutionCreateRequest(),
    )
    first_claim = claim_next_execution(database)
    assert first_claim is not None
    run_claimed_execution(database, settings, first_claim)
    database.refresh(execution)
    assert execution.status is ExecutionStatus.CREATED
    second_claim = claim_next_execution(database)
    assert second_claim is not None
    run_claimed_execution(database, settings, second_claim)
    database.refresh(execution)
    assert execution.status is ExecutionStatus.FAILED
    assert execution.attempt_count == 2


def test_canceled_execution_does_not_retry(database: Session) -> None:
    user, report = _create_report(database)
    settings = _settings()
    execution = create_execution(
        database,
        settings,
        report.organization_id,
        user.id,
        Role.ORGANIZATION_ADMIN,
        report.id,
        ExecutionCreateRequest(),
    )
    claimed = claim_next_execution(database)
    assert claimed is not None
    claimed.status = ExecutionStatus.CANCELED
    database.commit()
    run_claimed_execution(database, settings, claimed)
    database.refresh(execution)
    assert execution.status is ExecutionStatus.CANCELED
    assert execution.attempt_count == 1


def test_execution_timeout_is_normalized() -> None:
    with pytest.raises(DomainError) as error:
        _check_timeout(0, _settings().model_copy(update={"execution_timeout_seconds": 1}))
    assert error.value.code == "execution_timeout"
