from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProposalRequest(BaseModel):
    configuration_id: UUID
    objective: str = Field(min_length=3, max_length=5000)
    catalog_context: dict[str, Any] = Field(default_factory=dict)


class ProposalResponse(BaseModel):
    name: str
    objective: str | None = None
    definition: dict[str, Any]
