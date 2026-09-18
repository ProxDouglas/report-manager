from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import GrantTargetType, ReportStatus, ReportVersionStatus
from app.schemas.common import DTO


class ReportCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    objective: str | None = Field(default=None, max_length=5000)
    definition: dict[str, Any] = Field(default_factory=dict)


class ReportUpdateRequest(BaseModel):
    change_summary: str = Field(min_length=3, max_length=1000)
    definition: dict[str, Any]


class ReportResponse(DTO):
    id: UUID
    name: str
    objective: str | None
    status: ReportStatus
    published_version_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ReportVersionResponse(DTO):
    id: UUID
    report_id: UUID
    version_number: int
    status: ReportVersionStatus
    definition: dict[str, Any]
    change_summary: str | None
    published_at: datetime | None
    created_at: datetime


class ReportGrantCreateRequest(BaseModel):
    target_type: GrantTargetType
    target_id: str = Field(min_length=1, max_length=160)
    permission: str = Field(default="VIEW", min_length=1, max_length=40)


class ReportGrantResponse(DTO):
    id: UUID
    report_id: UUID
    target_type: GrantTargetType
    target_id: str
    permission: str
    created_at: datetime
