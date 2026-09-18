from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.sensitive import scrub_mapping
from app.db.enums import AuditResult
from app.db.models import AuditEvent, utc_now


def record_audit(
    db: Session,
    *,
    action: str,
    result: AuditResult,
    organization_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        correlation_id=correlation_id or str(db.info.get("correlation_id") or uuid4()),
        details=scrub_mapping(details or {}),
        created_at=utc_now(),
    )
    db.add(event)
    return event
