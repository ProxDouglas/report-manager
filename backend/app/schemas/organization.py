from datetime import date

from pydantic import BaseModel, Field


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    admin_email: str = Field(min_length=3, max_length=320)
    admin_name: str = Field(min_length=2, max_length=160)
    temporary_password: str = Field(min_length=12, max_length=256)
    starts_on: date | None = None
    ends_on: date | None = None


class LicenseChangeRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
