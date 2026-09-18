from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import ArtifactType, ExecutionStatus
from app.schemas.common import DTO


class ExecutionCreateRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=160)


class ArtifactResponse(DTO):
    id: UUID
    artifact_type: ArtifactType
    storage_key: str
    file_name: str
    content_type: str
    checksum: str
    size_bytes: int
    expires_at: datetime


class ExecutionResponse(DTO):
    id: UUID
    report_id: UUID
    report_version_id: UUID
    status: ExecutionStatus
    parameters: dict[str, Any]
    attempt_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error_summary: str | None
    created_at: datetime
    artifacts: list[ArtifactResponse] = Field(default_factory=list)


class ReadyReportResponse(BaseModel):
    execution: ExecutionResponse
    report_name: str
    version_number: int
