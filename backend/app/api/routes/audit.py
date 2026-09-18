from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import RequestContext, require_application_context
from app.db.models import AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    action: str | None = Query(default=None, max_length=120),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    context: RequestContext = Depends(require_application_context),  # noqa: B008
) -> list[dict[str, object]]:
    query = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == context.organization.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(200)
    )
    if action:
        query = query.where(AuditEvent.action == action)
    if from_date:
        query = query.where(AuditEvent.created_at >= from_date)
    if to_date:
        query = query.where(AuditEvent.created_at <= to_date)
    events = context.db.scalars(query).all()
    return [
        {
            "id": event.id,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "result": event.result,
            "correlation_id": event.correlation_id,
            "details": event.details,
            "created_at": event.created_at,
        }
        for event in events
    ]
