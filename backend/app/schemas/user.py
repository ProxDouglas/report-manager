from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import Role
from app.schemas.common import DTO


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=2, max_length=160)
    temporary_password: str = Field(min_length=12, max_length=256)
    role: Role = Role.VIEWER


class MembershipResponse(DTO):
    id: UUID
    user_id: UUID
    email: str
    display_name: str
    role: Role
    is_active: bool


class MembershipChangeRequest(BaseModel):
    role: Role
    is_active: bool = True
