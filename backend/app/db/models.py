from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base
from app.db.enums import (
    ArtifactType,
    AuditResult,
    DataClassification,
    DestinationStatus,
    DestinationType,
    ExecutionStatus,
    GrantTargetType,
    LicenseStatus,
    LlmProvider,
    OrganizationStatus,
    OutboxStatus,
    ReportStatus,
    ReportVersionStatus,
    Role,
    SensitivityAction,
    SourceStatus,
    SourceType,
    SourceVersionStatus,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def enum_type(enum_class: type) -> SqlEnum:
    return SqlEnum(enum_class, native_enum=False, validate_strings=True)


JsonType = JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    status: Mapped[OrganizationStatus] = mapped_column(
        enum_type(OrganizationStatus), nullable=False
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_platform_operator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership_organization_user"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Role] = mapped_column(enum_type(Role), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class License(TimestampMixin, Base):
    __tablename__ = "licenses"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_license_organization"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[LicenseStatus] = mapped_column(enum_type(LicenseStatus), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    limits: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_token_hash", "token_hash"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    active_organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_organization_created", "organization_id", "created_at"),
        Index("ix_audit_events_action_created", "action", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    result: Mapped[AuditResult] = mapped_column(enum_type(AuditResult), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DataSource(TimestampMixin, Base):
    __tablename__ = "data_sources"
    __table_args__ = (Index("ix_data_sources_organization_status", "organization_id", "status"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(enum_type(SourceType), nullable=False)
    status: Mapped[SourceStatus] = mapped_column(enum_type(SourceStatus), nullable=False)
    connection_config: Mapped[dict[str, Any]] = mapped_column(
        JsonType, default=dict, nullable=False
    )
    import_config: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    secret_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataSourceVersion(Base):
    __tablename__ = "data_source_versions"
    __table_args__ = (
        UniqueConstraint("data_source_id", "version_number", name="uq_source_version_number"),
        Index("ix_source_versions_source_valid", "data_source_id", "is_latest_valid"),
        Index(
            "uq_source_latest_valid",
            "data_source_id",
            unique=True,
            postgresql_where=sql_text("is_latest_valid = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    data_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SourceVersionStatus] = mapped_column(
        enum_type(SourceVersionStatus), nullable=False
    )
    is_latest_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schema_snapshot: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    import_config: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class SourceGrant(Base):
    __tablename__ = "source_grants"
    __table_args__ = (
        UniqueConstraint(
            "data_source_id", "target_type", "target_id", name="uq_source_grant_target"
        ),
        Index("ix_source_grants_source_target", "data_source_id", "target_type", "target_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    data_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[GrantTargetType] = mapped_column(enum_type(GrantTargetType), nullable=False)
    target_id: Mapped[str] = mapped_column(String(160), nullable=False)
    permission: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class CatalogObject(Base):
    __tablename__ = "catalog_objects"
    __table_args__ = (
        UniqueConstraint("source_version_id", "object_name", name="uq_catalog_object_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_source_versions.id", ondelete="CASCADE"), nullable=False
    )
    object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class CatalogField(Base):
    __tablename__ = "catalog_fields"
    __table_args__ = (
        UniqueConstraint("catalog_object_id", "field_name", name="uq_catalog_field_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    catalog_object_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_objects.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(80), nullable=False)
    classification: Mapped[DataClassification] = mapped_column(
        enum_type(DataClassification), nullable=False
    )
    sensitivity_action: Mapped[SensitivityAction] = mapped_column(
        enum_type(SensitivityAction), nullable=False
    )
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    detection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Report(TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_organization_status", "organization_id", "status"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReportStatus] = mapped_column(enum_type(ReportStatus), nullable=False)
    published_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "report_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_reports_published_version",
        ),
        nullable=True,
    )


class ReportVersion(Base):
    __tablename__ = "report_versions"
    __table_args__ = (
        UniqueConstraint("report_id", "version_number", name="uq_report_version_number"),
        Index("ix_report_versions_report_status", "report_id", "status"),
        Index(
            "uq_report_published_version",
            "report_id",
            unique=True,
            postgresql_where=sql_text("status = 'PUBLICADO'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReportVersionStatus] = mapped_column(
        enum_type(ReportVersionStatus), nullable=False
    )
    definition: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ReportGrant(Base):
    __tablename__ = "report_grants"
    __table_args__ = (
        UniqueConstraint("report_id", "target_type", "target_id", name="uq_report_grant_target"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[GrantTargetType] = mapped_column(enum_type(GrantTargetType), nullable=False)
    target_id: Mapped[str] = mapped_column(String(160), nullable=False)
    permission: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Execution(TimestampMixin, Base):
    __tablename__ = "executions"
    __table_args__ = (
        Index(
            "ix_executions_organization_status_created", "organization_id", "status", "created_at"
        ),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_execution_idempotency"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="RESTRICT"), nullable=False
    )
    report_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("report_versions.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[ExecutionStatus] = mapped_column(enum_type(ExecutionStatus), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"
    __table_args__ = (
        UniqueConstraint("execution_id", "attempt_number", name="uq_execution_attempt_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(enum_type(ExecutionStatus), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)


class ExecutionSourceVersion(Base):
    __tablename__ = "execution_source_versions"
    __table_args__ = (UniqueConstraint("execution_id", "source_id", name="uq_execution_source"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("data_source_versions.id", ondelete="RESTRICT"), nullable=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    schema_snapshot: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (Index("ix_artifacts_execution_type", "execution_id", "artifact_type"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )
    report_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("report_versions.id", ondelete="RESTRICT"), nullable=False
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(enum_type(ArtifactType), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class LlmPreset(TimestampMixin, Base):
    __tablename__ = "llm_presets"
    __table_args__ = (
        UniqueConstraint("provider", "model_identifier", name="uq_llm_preset_provider_model"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[LlmProvider] = mapped_column(enum_type(LlmProvider), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    reasoning_levels: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LlmConfiguration(TimestampMixin, Base):
    __tablename__ = "llm_configurations"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_llm_configuration_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    preset_id: Mapped[UUID] = mapped_column(
        ForeignKey("llm_presets.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    reasoning_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    capability_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JsonType, default=dict, nullable=False
    )


class LlmInvocation(Base):
    __tablename__ = "llm_invocations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    configuration_id: Mapped[UUID] = mapped_column(
        ForeignKey("llm_configurations.id", ondelete="RESTRICT"), nullable=False
    )
    execution_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[LlmProvider] = mapped_column(enum_type(LlmProvider), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(160), nullable=False)
    reasoning_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    usage_metadata: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Destination(TimestampMixin, Base):
    __tablename__ = "destinations"
    __table_args__ = (
        Index("ix_destinations_organization_type", "organization_id", "destination_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    destination_type: Mapped[DestinationType] = mapped_column(
        enum_type(DestinationType), nullable=False
    )
    status: Mapped[DestinationStatus] = mapped_column(enum_type(DestinationStatus), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    secret_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_events_status_created", "status", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(enum_type(OutboxStatus), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_name: Mapped[str] = mapped_column(String(120), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ATIVO")
    worker_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonType, default=dict, nullable=False
    )
