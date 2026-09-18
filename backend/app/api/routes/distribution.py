from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import RequestContext, require_roles
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.db.enums import Role
from app.db.models import Destination
from app.schemas.destination import (
    DestinationCreateRequest,
    DestinationResponse,
    DestinationStatusRequest,
)
from app.services.distribution import create_destination, distribute

router = APIRouter(prefix="/destinations", tags=["distribution"])
admin = require_roles(Role.ORGANIZATION_ADMIN)
reader = require_roles(Role.ORGANIZATION_ADMIN, Role.REPORT_CREATOR)


@router.get("", response_model=list[DestinationResponse])
def list_destinations(context: RequestContext = Depends(admin)) -> list[DestinationResponse]:  # noqa: B008
    destinations = context.db.scalars(
        select(Destination)
        .where(Destination.organization_id == context.organization.id)
        .order_by(Destination.name)
    ).all()
    return [DestinationResponse.model_validate(destination) for destination in destinations]


@router.post("", response_model=DestinationResponse, status_code=201)
def add_destination(
    payload: DestinationCreateRequest, context: RequestContext = Depends(admin)
) -> DestinationResponse:  # noqa: B008
    return DestinationResponse.model_validate(
        create_destination(context.db, context.organization.id, context.user.id, payload)
    )


@router.patch("/{destination_id}", response_model=DestinationResponse)
def change_destination_status(
    destination_id: UUID,
    payload: DestinationStatusRequest,
    context: RequestContext = Depends(admin),  # noqa: B008
) -> DestinationResponse:
    destination = context.db.scalar(
        select(Destination).where(
            Destination.id == destination_id,
            Destination.organization_id == context.organization.id,
        )
    )
    if not destination:
        raise NotFoundError("Destino não encontrado.")
    destination.status = payload.status
    context.db.commit()
    context.db.refresh(destination)
    return DestinationResponse.model_validate(destination)


@router.post("/{destination_id}/executions/{execution_id}/send")
def send_destination(
    destination_id: UUID,
    execution_id: UUID,
    context: RequestContext = Depends(reader),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, object]:
    return distribute(
        context.db, settings, context.organization.id, context.user.id, destination_id, execution_id
    )
