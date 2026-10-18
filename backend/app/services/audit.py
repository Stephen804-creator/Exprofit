"""Helpers for recording durable workspace audit events."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_audit_event(
    db: Session,
    *,
    business_id: UUID,
    actor_user_id: UUID | None,
    event_type: str,
    target_type: str,
    target_id: UUID | str,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Stage an audit event in the caller's transaction; caller commits atomically."""
    event = AuditEvent(
        business_id=business_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type=target_type,
        target_id=str(target_id),
        reason=reason,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event
