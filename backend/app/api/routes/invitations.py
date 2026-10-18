"""Shareable invitations with owner-reviewed identity applications."""

import base64
import binascii
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
from app.models import (
    Business,
    BusinessMembership,
    InvitationApplication,
    User,
    WorkspaceInvitation,
)
from app.permissions import require_permission, validate_permission_delegation
from app.schemas.invitations import (
    InvitationApplicationCreate,
    InvitationApplicationDecision,
    InvitationApplicationDecisionRead,
    InvitationApplicationRead,
    InvitationCreate,
    InvitationRead,
)
from app.services.audit import record_audit_event

router = APIRouter(tags=["workspace invitations"])
MAX_PHOTO_BYTES = 2 * 1024 * 1024


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _unavailable(invitation: WorkspaceInvitation | None, now: datetime) -> bool:
    return (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.revoked_at is not None
        or _utc(invitation.expires_at) <= now
    )


def _decode_photo(data_url: str) -> bytes:
    prefix = "data:image/jpeg;base64,"
    if not data_url.startswith(prefix):
        raise HTTPException(status_code=422, detail="Capture or select a JPEG face photo")
    try:
        photo = base64.b64decode(data_url[len(prefix):], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="The photo could not be read") from exc
    if not photo or len(photo) > MAX_PHOTO_BYTES or not photo.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=422, detail="Photo must be a valid JPEG up to 2 MB")
    return photo


def _read_application(
    db: Session,
    application: InvitationApplication,
    invitation: WorkspaceInvitation,
) -> InvitationApplicationRead:
    user = db.get(User, application.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Applicant account not found")
    return InvitationApplicationRead(
        id=application.id, invitation_id=invitation.id, full_name=application.full_name,
        email=user.email,
        phone=application.phone,
        identifying_details=application.identifying_details,
        role=invitation.role, status=application.status, created_at=application.created_at,
    )


@router.post(
    "/businesses/{business_id}/invitations",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    business_id: UUID, payload: InvitationCreate,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)],
) -> InvitationRead:
    """Create a unique link the owner can copy and share through any channel."""
    require_permission(actor, "staff_administration", "write")
    business = db.get(Business, business_id)
    if business is None or business.workspace_type != "business":
        raise HTTPException(status_code=404, detail="Business workspace not found")
    grants = validate_permission_delegation(actor, payload.role, payload.permissions)
    raw_token = secrets.token_urlsafe(32)
    invitation = WorkspaceInvitation(
        business_id=business_id, recipient_email=None, role=payload.role, permissions=grants,
        token_hash=sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(hours=payload.expires_in_hours),
        created_by_user_id=user.id,
    )
    db.add(invitation)
    db.flush()
    record_audit_event(
        db, business_id=business_id, actor_user_id=user.id, event_type="invitation.created",
        target_type="workspace_invitation", target_id=invitation.id,
        metadata={"role": payload.role, "expires_in_hours": payload.expires_in_hours},
    )
    db.commit()
    db.refresh(invitation)
    base_url = get_settings().frontend_base_url.rstrip("/")
    return InvitationRead(
        id=invitation.id, business_id=business_id, recipient_email=None, role=invitation.role,
        permissions=invitation.permissions, expires_at=invitation.expires_at,
        invitation_url=f"{base_url}/accept-invitation?token={raw_token}",
    )


@router.post("/invitations/apply", response_model=InvitationApplicationRead, status_code=201)
def submit_application(
    payload: InvitationApplicationCreate, user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationApplicationRead:
    """Submit identifying details and a private photo; no access is granted yet."""
    token_hash = sha256(payload.token.encode()).hexdigest()
    invitation = db.scalar(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.token_hash == token_hash)
        .with_for_update()
    )
    now = datetime.now(UTC)
    if _unavailable(invitation, now):
        raise HTTPException(status_code=400, detail="Invalid, expired, or unavailable invitation")
    assert invitation is not None
    business = db.get(Business, invitation.business_id)
    if business is None or business.workspace_type != "business":
        raise HTTPException(status_code=400, detail="Invitation workspace is unavailable")
    membership = db.scalar(select(BusinessMembership).where(
        BusinessMembership.business_id == invitation.business_id,
        BusinessMembership.user_id == user.id
    ))
    if membership is not None and membership.status == "active":
        raise HTTPException(status_code=409, detail="You already belong to this workspace")
    application = InvitationApplication(
        invitation_id=invitation.id, user_id=user.id, full_name=payload.full_name,
        phone=payload.phone, identifying_details=payload.identifying_details,
        photo_bytes=_decode_photo(payload.photo_data_url), status="pending",
    )
    db.add(application)
    record_audit_event(
        db, business_id=invitation.business_id, actor_user_id=user.id,
        event_type="invitation.application_submitted", target_type="invitation_application",
        target_id=application.id, metadata={"role": invitation.role},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An application has already been submitted for this invitation",
        ) from exc
    db.refresh(application)
    return _read_application(db, application, invitation)


@router.get(
    "/businesses/{business_id}/invitation-applications",
    response_model=list[InvitationApplicationRead],
)
def list_applications(
    business_id: UUID, actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> list[InvitationApplicationRead]:
    """List pending applications for authorized workspace administrators."""
    require_permission(actor, "staff_administration", "read")
    business = db.get(Business, business_id)
    if business is None or business.workspace_type != "business":
        raise HTTPException(status_code=404, detail="Business workspace not found")
    now = datetime.now(UTC)
    rows = db.execute(
        select(InvitationApplication, WorkspaceInvitation)
        .join(WorkspaceInvitation, WorkspaceInvitation.id == InvitationApplication.invitation_id)
        .where(
            WorkspaceInvitation.business_id == business_id,
            InvitationApplication.status == "pending",
            WorkspaceInvitation.accepted_at.is_(None), WorkspaceInvitation.revoked_at.is_(None),
            WorkspaceInvitation.expires_at > now,
        ).order_by(InvitationApplication.created_at.desc())
    ).all()
    return [_read_application(db, app, inv) for app, inv in rows]


@router.get("/businesses/{business_id}/invitation-applications/{application_id}/photo")
def read_application_photo(
    business_id: UUID, application_id: UUID,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Only authorized administrators can view a pending applicant's photo."""
    require_permission(actor, "staff_administration", "read")
    application = db.scalar(
        select(InvitationApplication)
        .join(WorkspaceInvitation, WorkspaceInvitation.id == InvitationApplication.invitation_id)
        .where(
            InvitationApplication.id == application_id,
            WorkspaceInvitation.business_id == business_id,
            InvitationApplication.status == "pending",
        )
    )
    if application is None or application.photo_bytes is None:
        raise HTTPException(status_code=404, detail="Pending application photo not found")
    return Response(
        content=application.photo_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/businesses/{business_id}/invitation-applications/{application_id}/approve",
    response_model=InvitationApplicationDecisionRead,
)
def approve_application(
    business_id: UUID, application_id: UUID,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationApplicationDecisionRead:
    """Approve an application and activate the invited member."""
    require_permission(actor, "staff_administration", "write")
    application = db.scalar(
        select(InvitationApplication)
        .join(WorkspaceInvitation, WorkspaceInvitation.id == InvitationApplication.invitation_id)
        .where(
            InvitationApplication.id == application_id,
            WorkspaceInvitation.business_id == business_id,
        )
        .with_for_update()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Invitation application not found")
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="Application has already been reviewed")
    invitation = db.get(WorkspaceInvitation, application.invitation_id)
    now = datetime.now(UTC)
    if _unavailable(invitation, now):
        raise HTTPException(
            status_code=409,
            detail="Invitation is expired, revoked, or already used",
        )
    assert invitation is not None
    applicant = db.get(User, application.user_id)
    if applicant is None or not applicant.is_active:
        raise HTTPException(status_code=409, detail="Applicant account is unavailable")
    membership = db.scalar(select(BusinessMembership).where(
        BusinessMembership.business_id == business_id, BusinessMembership.user_id == applicant.id
    ))
    if membership is not None and membership.status == "active":
        raise HTTPException(status_code=409, detail="Applicant is already a workspace member")
    if membership is None:
        membership = BusinessMembership(
            business_id=business_id, user_id=applicant.id, role=invitation.role,
            status="active", permissions=invitation.permissions,
        )
        db.add(membership)
    else:
        membership.role = invitation.role
        membership.permissions = invitation.permissions
        membership.status = "active"
        membership.suspended_until = None
        membership.revoked_at = None
        membership.leave_effective_at = None
        membership.leave_reason = None
    invitation.accepted_at = now
    invitation.accepted_by_user_id = applicant.id
    application.status = "approved"
    application.reviewed_by_user_id = actor.user_id
    application.reviewed_at = now
    application.photo_bytes = None
    record_audit_event(
        db, business_id=business_id, actor_user_id=actor.user_id,
        event_type="invitation.application_approved", target_type="invitation_application",
        target_id=application.id, metadata={"role": invitation.role},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Application could not be approved") from exc
    return InvitationApplicationDecisionRead(
        application_id=application.id, status="approved", business_id=business_id,
        role=invitation.role, message="Applicant approved and added to the workspace.",
    )


@router.post(
    "/businesses/{business_id}/invitation-applications/{application_id}/reject",
    response_model=InvitationApplicationDecisionRead,
)
def reject_application(
    business_id: UUID, application_id: UUID, payload: InvitationApplicationDecision,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationApplicationDecisionRead:
    """Reject an application, revoke its link, and discard its photo."""
    require_permission(actor, "staff_administration", "write")
    application = db.scalar(
        select(InvitationApplication)
        .join(WorkspaceInvitation, WorkspaceInvitation.id == InvitationApplication.invitation_id)
        .where(
            InvitationApplication.id == application_id,
            WorkspaceInvitation.business_id == business_id,
        )
        .with_for_update()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Invitation application not found")
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="Application has already been reviewed")
    invitation = db.get(WorkspaceInvitation, application.invitation_id)
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    now = datetime.now(UTC)
    application.status = "rejected"
    application.reviewed_by_user_id = actor.user_id
    application.reviewed_at = now
    application.photo_bytes = None
    invitation.revoked_at = now
    record_audit_event(
        db, business_id=business_id, actor_user_id=actor.user_id,
        event_type="invitation.application_rejected", target_type="invitation_application",
        target_id=application.id, reason=payload.reason,
    )
    db.commit()
    return InvitationApplicationDecisionRead(
        application_id=application.id, status="rejected",
        message="Application rejected; invitation can no longer be used.",
    )


@router.post(
    "/businesses/{business_id}/invitations/{invitation_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_invitation(
    business_id: UUID, invitation_id: UUID,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Revoke a link and discard any pending photo application."""
    require_permission(actor, "staff_administration", "write")
    invitation = db.scalar(select(WorkspaceInvitation).where(
        WorkspaceInvitation.id == invitation_id, WorkspaceInvitation.business_id == business_id
    ).with_for_update())
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Accepted invitations cannot be revoked")
    if invitation.revoked_at is None:
        now = datetime.now(UTC)
        invitation.revoked_at = now
        application = db.scalar(
            select(InvitationApplication).where(
                InvitationApplication.invitation_id == invitation.id,
                InvitationApplication.status == "pending",
            )
        )
        if application is not None:
            application.status = "rejected"
            application.reviewed_by_user_id = actor.user_id
            application.reviewed_at = now
            application.photo_bytes = None
        record_audit_event(
            db, business_id=business_id, actor_user_id=actor.user_id,
            event_type="invitation.revoked",
            target_type="workspace_invitation",
            target_id=invitation.id,
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
