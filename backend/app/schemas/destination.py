from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.db.enums import DestinationStatus, DestinationType
from app.schemas.common import DTO


class DestinationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    destination_type: DestinationType
    configuration: dict[str, Any] = Field(default_factory=dict)
    secret_ref: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_configuration(self) -> "DestinationCreateRequest":
        if self.destination_type is DestinationType.EMAIL:
            recipients = self.configuration.get("recipients")
            if not isinstance(recipients, list) or not recipients:
                raise ValueError("Destino de e-mail exige recipients.")
        if self.destination_type is DestinationType.WEBHOOK:
            url = self.configuration.get("url")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                raise ValueError("Webhook exige URL HTTP ou HTTPS.")
            if not self.secret_ref:
                raise ValueError("Webhook exige secret_ref para assinatura.")
        return self


class DestinationResponse(DTO):
    id: UUID
    name: str
    destination_type: DestinationType
    status: DestinationStatus
    configuration: dict[str, Any]
    secret_ref: str | None


class DestinationStatusRequest(BaseModel):
    status: DestinationStatus
