from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import Role


class DTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Any | None = None


class UserResponse(DTO):
    id: UUID
    email: str
    display_name: str
    must_change_password: bool
    is_platform_operator: bool
    is_active: bool


class LicenseResponse(DTO):
    id: UUID
    status: str
    starts_on: date
    ends_on: date | None
    reason: str | None


class OrganizationResponse(DTO):
    id: UUID
    name: str
    slug: str
    status: str
    license: LicenseResponse | None = None


class SessionResponse(BaseModel):
    user: UserResponse
    organizations: list[OrganizationResponse]
    active_organization_id: UUID | None
    active_role: Role | None = None


class Pagination(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
