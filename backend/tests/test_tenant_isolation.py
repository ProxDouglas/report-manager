from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.db.enums import (
    ArtifactType,
    ExecutionStatus,
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
    Execution,
    License,
    Membership,
    Organization,
    Report,
    ReportVersion,
    User,
)
from app.schemas.execution import ExecutionCreateRequest
from app.services.artifact_service import get_downloadable_artifact
from app.services.execution_service import create_execution
from app.services.report_service import ensure_report
from app.services.source_service import ensure_source


def test_resources_cannot_cross_organizations(database: Session) -> None:
    organization_a = Organization(name="A", slug="a", status=OrganizationStatus.ACTIVE)
    organization_b = Organization(name="B", slug="b", status=OrganizationStatus.ACTIVE)
    user_a = User(
        email="a@example.com",
        display_name="A",
        password_hash="hash",
        must_change_password=False,
    )
    database.add_all([organization_a, organization_b, user_a])
    database.flush()
    database.add_all(
        [
            License(
                organization_id=organization_a.id,
                status="ATIVA",
                starts_on=date.today(),
            ),
            Membership(
                organization_id=organization_a.id,
                user_id=user_a.id,
                role=Role.ORGANIZATION_ADMIN,
            ),
        ]
    )
    source = DataSource(
        organization_id=organization_a.id,
        owner_user_id=user_a.id,
        name="Fonte A",
        source_type=SourceType.CSV,
        status=SourceStatus.ACTIVE,
    )
    database.add(source)
    database.flush()
    source_version = DataSourceVersion(
        data_source_id=source.id,
        version_number=1,
        status=SourceVersionStatus.VALID,
        is_latest_valid=True,
        content=b"a,b\n1,2\n",
        schema_snapshot={"columns": [{"name": "a", "type": "integer"}]},
        created_by_user_id=user_a.id,
    )
    database.add(source_version)
    report = Report(
        organization_id=organization_a.id,
        created_by_user_id=user_a.id,
        name="Relatório A",
        objective="Teste",
        status=ReportStatus.PUBLISHED,
    )
    database.add(report)
    database.flush()
    version = ReportVersion(
        report_id=report.id,
        version_number=1,
        status=ReportVersionStatus.PUBLISHED,
        definition={"source_id": str(source.id)},
        created_by_user_id=user_a.id,
    )
    database.add(version)
    database.flush()
    report.published_version_id = version.id
    execution = Execution(
        organization_id=organization_a.id,
        report_id=report.id,
        report_version_id=version.id,
        requested_by_user_id=user_a.id,
        status=ExecutionStatus.SUCCESS,
        idempotency_key=str(uuid4()),
    )
    database.add(execution)
    database.flush()
    artifact = Artifact(
        organization_id=organization_a.id,
        execution_id=execution.id,
        report_version_id=version.id,
        artifact_type=ArtifactType.CSV,
        storage_key="postgres://artifacts/test",
        file_name="test.csv",
        content_type="text/csv",
        content=b"a,b\n1,2\n",
        checksum="checksum",
        size_bytes=8,
        expires_at=execution.created_at,
    )
    database.add(artifact)
    database.commit()

    with pytest.raises(NotFoundError):
        ensure_source(database, organization_b.id, source.id)
    with pytest.raises(NotFoundError):
        ensure_report(database, organization_b.id, report.id)
    with pytest.raises(NotFoundError):
        get_downloadable_artifact(database, organization_b.id, artifact.id)
    with pytest.raises(NotFoundError):
        create_execution(
            database,
            Settings(app_env="test", database_url="sqlite://"),
            organization_b.id,
            user_a.id,
            Role.VIEWER,
            report.id,
            ExecutionCreateRequest(),
        )
