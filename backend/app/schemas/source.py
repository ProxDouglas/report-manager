from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.db.enums import (
    DataClassification,
    GrantTargetType,
    SensitivityAction,
    SourceStatus,
    SourceType,
)
from app.schemas.common import DTO


class ConnectionConfig(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(gt=0, le=65535)
    database: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    schema_name: str | None = Field(default=None, max_length=255)
    allowed_tables: list[str] = Field(default_factory=list, max_length=200)
    tls_verify: bool = True


class SourceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    source_type: SourceType
    connection: ConnectionConfig | None = None
    secret_ref: str | None = Field(default=None, max_length=512)
    import_config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source_payload(self) -> "SourceCreateRequest":
        database_type = {
            SourceType.POSTGRESQL,
            SourceType.ORACLE,
            SourceType.SQLSERVER,
        }
        if self.source_type in database_type and (self.connection is None or not self.secret_ref):
            raise ValueError("Fontes de banco exigem conexão e secret_ref.")
        if self.source_type not in database_type and self.connection is not None:
            raise ValueError("Fontes de arquivo não aceitam conexão de banco.")
        return self


class SourceResponse(DTO):
    id: UUID
    name: str
    source_type: SourceType
    status: SourceStatus
    last_tested_at: datetime | None
    last_test_error: str | None


class SourceVersionResponse(DTO):
    id: UUID
    data_source_id: UUID
    version_number: int
    status: str
    is_latest_valid: bool
    file_name: str | None
    content_type: str | None
    checksum: str | None
    schema_snapshot: dict[str, Any]
    created_at: datetime


class SourceTestResponse(BaseModel):
    success: bool
    message: str
    schema_snapshot: dict[str, Any] = Field(default_factory=dict)


class CatalogFieldUpdateRequest(BaseModel):
    classification: DataClassification
    sensitivity_action: SensitivityAction


class SourceGrantCreateRequest(BaseModel):
    target_type: GrantTargetType
    target_id: str = Field(min_length=1, max_length=160)
    permission: str = Field(default="VIEW", min_length=1, max_length=40)


class SourceGrantResponse(DTO):
    id: UUID
    data_source_id: UUID
    target_type: GrantTargetType
    target_id: str
    permission: str
    created_at: datetime
