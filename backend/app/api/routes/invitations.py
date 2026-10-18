"""Create, revoke, and accept secure workspace invitations."""

import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_business_membership
from app.config import get_settings
from app.db.session import get_db
from app.email_delivery import EmailDeliveryError, send_invitation_email
from app.models import Business, BusinessMembership, User, WorkspaceInvitation
from app.permissions import require_permission
from app.services.audit import record_audit_event
from app.schemas.invitations import (
    ALLOWED_PERMISSION_KEYS,
    InvitationAccepted,
    InvitationAcceptRequest,
    InvitationCreate,
    InvitationRead,
)

router = APIRouter(tags=["workspace invitations"])


def _utc(value: datetime) -> datetime:
    """Treat naive SQLite timestamps as UTC for consistent expiry checks."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _validate_delegation(
    actor: BusinessMembership,
    requested_role: str,
    requested_permissions: dict[str, bool],
) -> dict[str, bool]:
    """Prevent admins from granting privileges they do not hold themselves."""
    grants = {key: value for key, value in requested_permissions.items() if value}
    unknown = set(grants) - ALLOWED_PERMISSION_KEYS
    if unknown:
        raise HTTPException(status_code=422, detail="Unsupported permission grant")

    if requested_role == "worker" and any(
        key.startswith("staff_administration:") for key in grants
    ):
        raise HTTPException(
            status_code=422,
            detail="Staff Administration permissions can only be granted to authorized admins",
        )

    if actor.role != "owner":
        if requested_role != "worker":
            raise HTTPException(
                status_code=403,
                detail="Only the workspace owner can invite an admin",
            )
        own_grants = {
            key for key, value in (actor.permissions or {}).items() if value is True
        }
        if not grants.issubset(own_grants):
            raise HTTPException(
                status_code=403,
                detail="You cannot grant permissions you do not hold",
            )
        if any(key.startswith("staff_administration:") for key in grants):
            raise HTTPException(
                status_code=403,
                detail="Admins cannot delegate Staff Administration access",
            )
    return grants


@router.post(
    "/businesses/{business_id}/invitations",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    business_id: UUID,
    payload: InvitationCreate,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceInvitation:
    """Create and email a short-lived invitation to one exact email identity."""
    require_permission(actor, "staff_administration", "write")
    settings = get_settings()
    if not settings.email_delivery_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured",
        )

    business = db.get(Business, business_id)
    if business is None or business.workspace_type != "business":
        raise HTTPException(status_code=404, detail="Business workspace not found")

    grants = _validate_delegation(actor, payload.role, payload.permissions)
    existing_user = db.scalar(select(User).where(User.email == payload.recipient_email))
    if existing_user is not None:
        existing_membership = db.scalar(
            select(BusinessMembership).where(
                BusinessMembership.business_id == business_id,
                BusinessMembership.user_id == existing_user.id,
            )
        )
        if existing_membership is not None and existing_membership.status == "active":
            raise HTTPException(status_code=409, detail="Recipient is already a workspace member")

    now = datetime.now(UTC)
    previous = db.scalars(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.business_id == business_id,
            WorkspaceInvitation.recipient_email == payload.recipient_email,
            WorkspaceInvitation.accepted_at.is_(None),
            WorkspaceInvitation.revoked_at.is_(None),
        )
        .with_for_update()
    ).all()
    for old_invitation in previous:
        old_invitation.revoked_at = now

    raw_token = secrets.token_urlsafe(32)
    invitation = WorkspaceInvitation(
        business_id=business_id,
        recipient_email=payload.recipient_email,
        role=payload.role,
        permissions=grants,
        token_hash=sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=now + timedelta(minutes=settings.workspace_invitation_ttl_minutes),
        created_by_user_id=user.id,
    )
    db.add(invitation)
    db.flush()
    record_audit_event(
        db,
        business_id=business_id,
        actor_user_id=user.id,
        event_type="invitation.created",
        target_type="workspace_invitation",
        target_id=invitation.id,
        metadata={"recipient_email": payload.recipient_email, "role": payload.role},
    )
    db.commit()
    db.refresh(invitation)

    workspace_name = business.display_name or business.name
    invitation_url = (
        f"{settings.frontend_base_url.rstrip('/')}/accept-invitation?token={raw_token}"
    )
    try:
        send_invitation_email(
            payload.recipient_email,
            invitation_url,
            workspace_name,
            settings,
        )
    except EmailDeliveryError as exc:
        invitation.revoked_at = datetime.now(UTC)
        record_audit_event(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            event_type="invitation.revoked",
            target_type="workspace_invitation",
            target_id=invitation.id,
            reason="Email delivery failed",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invitation email could not be sent. Please try again later.",
        ) from exc
    return invitation


@router.post("/invitations/accept", response_model=InvitationAccepted)
def accept_invitation(
    payload: InvitationAcceptRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationAccepted:
    """Accept only if the signed-in account has the exact verified recipient email."""
    token_hash = sha256(payload.token.encode("utf-8")).hexdigest()
    invitation = db.scalar(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.token_hash == token_hash)
        .with_for_update()
    )
    now = datetime.now(UTC)
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.revoked_at is not None
        or _utc(invitation.expires_at) <= now
    ):
        raise HTTPException(status_code=400, detail="Invalid, expired, or unavailable invitation")

    if not user.email_verified:
        raise HTTPException(
            status_code=403,
            detail="Verify your email address before accepting workspace invitations",
        )
    if user.email.strip().lower() != invitation.recipient_email.strip().lower():
        raise HTTPException(
            status_code=403,
            detail="Sign in with the verified email address that received this invitation",
        )

    business = db.get(Business, invitation.business_id)
    if business is None or business.workspace_type != "business":
        raise HTTPException(status_code=400, detail="Invitation workspace is unavailable")

    membership = db.scalar(
        select(BusinessMembership).where(
            BusinessMembership.business_id == invitation.business_id,
            BusinessMembership.user_id == user.id,
        )
    )
    if membership is not None and membership.status == "active":
        raise HTTPException(status_code=409, detail="Already a member of this workspace")

    if membership is None:
        membership = BusinessMembership(
            business_id=invitation.business_id,
            user_id=user.id,
            role=invitation.role,
            status="active",
            permissions=invitation.permissions,
        )
        db.add(membership)
    else:
        membership.role = invitation.role
        membership.permissions = invitation.permissions
        membership.status = "active"
        membership.suspended_until = None
        membership.revoked_at = None

    invitation.accepted_at = now
    invitation.accepted_by_user_id = user.id
    record_audit_event(
        db,
        business_id=invitation.business_id,
        actor_user_id=user.id,
        event_type="invitation.accepted",
        target_type="workspace_invitation",
        target_id=invitation.id,
        metadata={"role": invitation.role},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invitation could not be accepted") from exc

    return InvitationAccepted(
        business_id=invitation.business_id,
        role=membership.role,
        status=membership.status,
    )


@router.post(
    "/businesses/{business_id}/invitations/{invitation_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_invitation(
    business_id: UUID,
    invitation_id: UUID,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Revoke a pending invitation before it is accepted."""
    require_permission(actor, "staff_administration", "write")
    invitation = db.scalar(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.id == invitation_id,
            WorkspaceInvitation.business_id == business_id,
        )
        .with_for_update()
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Accepted invitations cannot be revoked")
    if invitation.revoked_at is None:
        invitation.revoked_at = datetime.now(UTC)
        record_audit_event(
            db,
            business_id=business_id,
            actor_user_id=actor.user_id,
            event_type="invitation.revoked",
            target_type="workspace_invitation",
            target_id=invitation.id,
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
