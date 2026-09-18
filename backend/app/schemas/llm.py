from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import LlmProvider
from app.schemas.common import DTO


class PresetCreateRequest(BaseModel):
    provider: LlmProvider
    model_identifier: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=2, max_length=160)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    reasoning_levels: list[str] = Field(default_factory=list)
    max_tokens: int | None = Field(default=None, gt=0)


class PresetResponse(DTO):
    id: UUID
    provider: LlmProvider
    model_identifier: str
    name: str
    capabilities: dict[str, Any]
    reasoning_levels: list[str]
    max_tokens: int | None
    is_active: bool
    last_validated_at: datetime | None


class PresetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    capabilities: dict[str, Any] | None = None
    reasoning_levels: list[str] | None = None
    max_tokens: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class LlmConfigurationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    preset_id: UUID
    secret_ref: str = Field(min_length=5, max_length=512)
    reasoning_level: str | None = Field(default=None, max_length=40)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)


class LlmConfigurationResponse(DTO):
    id: UUID
    name: str
    preset_id: UUID
    secret_ref: str
    reasoning_level: str | None
    temperature: float | None
    max_tokens: int | None
    is_active: bool
