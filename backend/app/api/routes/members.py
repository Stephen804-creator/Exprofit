"""Business workspace member administration and audit-history endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_business_membership
from app.db.session import get_db
from app.models import AuditEvent, Business, BusinessMembership, User
from app.permissions import require_permission, validate_permission_delegation
from app.schemas.members import (
    AuditEventRead,
    MembershipRead,
    MembershipLeaveRequest,
    MembershipLeaveResponse,
    MembershipReason,
    MembershipSuspendRequest,
    MembershipUpdate,
)
from app.security import verify_password
from app.services.audit import record_audit_event

router = APIRouter(prefix="/businesses/{business_id}", tags=["workspace administration"])


def _ensure_business_workspace(db: Session, business_id: UUID) -> Business:
    business = db.get(Business, business_id)
    if business is None or business.workspace_type != "business":
        raise HTTPException(status_code=404, detail="Business workspace not found")
    return business


def _target_membership(
    db: Session,
    business_id: UUID,
    membership_id: UUID,
) -> BusinessMembership:
    membership = db.scalar(
        select(BusinessMembership).where(
            BusinessMembership.id == membership_id,
            BusinessMembership.business_id == business_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    return membership


def _apply_expired_suspension(db: Session, membership: BusinessMembership) -> bool:
    if membership.status != "suspended" or membership.suspended_until is None:
        return False
    expiry = membership.suspended_until
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry > datetime.now(UTC):
        return False

    membership.status = "active"
    membership.suspended_until = None
    membership.revoked_at = None
    record_audit_event(
        db,
        business_id=membership.business_id,
        actor_user_id=None,
        event_type="membership.auto_reinstated",
        target_type="business_membership",
        target_id=membership.id,
        reason="Timed suspension expired",
    )
    return True


def _check_target_authority(
    actor: BusinessMembership,
    target: BusinessMembership,
) -> None:
    if target.role == "owner":
        raise HTTPException(status_code=409, detail="Owner membership cannot be changed here")
    if target.user_id == actor.user_id:
        raise HTTPException(status_code=409, detail="You cannot change your own membership")
    if actor.role == "admin" and target.role != "worker":
        raise HTTPException(
            status_code=403,
            detail="Admins may manage Worker memberships only",
        )



def _apply_expired_leave(db: Session, membership: BusinessMembership) -> bool:
    if membership.status == "revoked" or membership.leave_effective_at is None:
        return False
    expiry = membership.leave_effective_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry > datetime.now(UTC):
        return False

    membership.status = "revoked"
    membership.revoked_at = datetime.now(UTC)
    membership.suspended_until = None
    record_audit_event(
        db,
        business_id=membership.business_id,
        actor_user_id=membership.user_id,
        event_type="membership.left",
        target_type="business_membership",
        target_id=membership.id,
        reason=membership.leave_reason or "Scheduled voluntary departure",
    )
    return True



def _refresh_target_lifecycle(db: Session, membership: BusinessMembership) -> bool:
    changed = _apply_expired_leave(db, membership)
    if not changed:
        changed = _apply_expired_suspension(db, membership)
    if changed:
        db.commit()
        db.refresh(membership)
    return changed


@router.get("/members", response_model=list[MembershipRead])
def list_members(
    business_id: UUID,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, object]]:
    """List members only for actors with explicit staff-administration read access."""
    require_permission(actor, "staff_administration", "read")
    _ensure_business_workspace(db, business_id)
    rows = db.execute(
        select(BusinessMembership, User.email)
        .join(User, User.id == BusinessMembership.user_id)
        .where(BusinessMembership.business_id == business_id)
        .order_by(BusinessMembership.created_at.asc())
    ).all()
    changed = False
    result: list[dict[str, object]] = []
    for membership, email in rows:
        lifecycle_changed = _apply_expired_leave(db, membership)
        if not lifecycle_changed:
            lifecycle_changed = _apply_expired_suspension(db, membership)
        changed = lifecycle_changed or changed
        result.append(
            {
                "membership_id": membership.id,
                "user_id": membership.user_id,
                "email": email,
                "role": membership.role,
                "status": membership.status,
                "permissions": membership.permissions or {},
                "created_at": membership.created_at,
                "suspended_until": membership.suspended_until,
                "revoked_at": membership.revoked_at,
                "leave_effective_at": membership.leave_effective_at,
            }
        )
    if changed:
        db.commit()
    return result


@router.patch("/members/{membership_id}", response_model=MembershipRead)
def update_member(
    business_id: UUID,
    membership_id: UUID,
    payload: MembershipUpdate,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Change a non-owner member's role/permissions with explicit delegation checks."""
    require_permission(actor, "staff_administration", "write")
    _ensure_business_workspace(db, business_id)
    target = _target_membership(db, business_id, membership_id)
    _refresh_target_lifecycle(db, target)
    _check_target_authority(actor, target)
    if target.status == "revoked":
        raise HTTPException(status_code=409, detail="Revoked members must accept a new invitation")

    old_role = target.role
    new_role = payload.role or target.role
    requested_permissions = (
        payload.permissions if payload.permissions is not None else target.permissions or {}
    )
    grants = validate_permission_delegation(actor, new_role, requested_permissions)
    target.role = new_role
    target.permissions = grants
    record_audit_event(
        db,
        business_id=business_id,
        actor_user_id=actor.user_id,
        event_type="membership.updated",
        target_type="business_membership",
        target_id=target.id,
        reason=payload.reason,
        metadata={
            "previous_role": old_role,
            "new_role": new_role,
            "granted_permissions": sorted(grants),
        },
    )
    db.commit()
    db.refresh(target)
    user = db.get(User, target.user_id)
    assert user is not None
    return {
        "membership_id": target.id,
        "user_id": target.user_id,
        "email": user.email,
        "role": target.role,
        "status": target.status,
        "permissions": target.permissions or {},
        "created_at": target.created_at,
        "suspended_until": target.suspended_until,
        "revoked_at": target.revoked_at,
        "leave_effective_at": target.leave_effective_at,
        "leave_effective_at": target.leave_effective_at,
    }


@router.post("/members/{membership_id}/suspend", response_model=MembershipRead)
def suspend_member(
    business_id: UUID,
    membership_id: UUID,
    payload: MembershipSuspendRequest,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Suspend a member immediately, optionally with a timed reinstatement."""
    require_permission(actor, "staff_administration", "write")
    _ensure_business_workspace(db, business_id)
    target = _target_membership(db, business_id, membership_id)
    _refresh_target_lifecycle(db, target)
    _check_target_authority(actor, target)
    if target.status == "revoked":
        raise HTTPException(status_code=409, detail="Revoked members cannot be suspended")
    now = datetime.now(UTC)
    target.status = "suspended"
    target.suspended_until = (
        now + timedelta(hours=payload.duration_hours)
        if payload.duration_hours is not None
        else None
    )
    target.revoked_at = None
    record_audit_event(
        db,
        business_id=business_id,
        actor_user_id=actor.user_id,
        event_type="membership.suspended",
        target_type="business_membership",
        target_id=target.id,
        reason=payload.reason,
        metadata={"duration_hours": payload.duration_hours},
    )
    db.commit()
    db.refresh(target)
    user = db.get(User, target.user_id)
    assert user is not None
    return {
        "membership_id": target.id,
        "user_id": target.user_id,
        "email": user.email,
        "role": target.role,
        "status": target.status,
        "permissions": target.permissions or {},
        "created_at": target.created_at,
        "suspended_until": target.suspended_until,
        "revoked_at": target.revoked_at,
    }


@router.post("/members/{membership_id}/revoke", response_model=MembershipRead)
def revoke_member(
    business_id: UUID,
    membership_id: UUID,
    payload: MembershipReason,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Revoke a member's access immediately without deleting financial history."""
    require_permission(actor, "staff_administration", "write")
    _ensure_business_workspace(db, business_id)
    target = _target_membership(db, business_id, membership_id)
    _apply_expired_suspension(db, target)
    _check_target_authority(actor, target)
    if target.status == "revoked":
        raise HTTPException(status_code=409, detail="Membership is already revoked")

    target.status = "revoked"
    target.suspended_until = None
    target.revoked_at = datetime.now(UTC)
    record_audit_event(
        db,
        business_id=business_id,
        actor_user_id=actor.user_id,
        event_type="membership.revoked",
        target_type="business_membership",
        target_id=target.id,
        reason=payload.reason,
    )
    db.commit()
    db.refresh(target)
    user = db.get(User, target.user_id)
    assert user is not None
    return {
        "membership_id": target.id,
        "user_id": target.user_id,
        "email": user.email,
        "role": target.role,
        "status": target.status,
        "permissions": target.permissions or {},
        "created_at": target.created_at,
        "suspended_until": target.suspended_until,
        "revoked_at": target.revoked_at,
    }


@router.post("/members/{membership_id}/reinstate", response_model=MembershipRead)
def reinstate_member(
    business_id: UUID,
    membership_id: UUID,
    payload: MembershipReason,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Reinstate a suspended member; revoked members must accept a new invitation."""
    require_permission(actor, "staff_administration", "write")
    _ensure_business_workspace(db, business_id)
    target = _target_membership(db, business_id, membership_id)
    _apply_expired_suspension(db, target)
    _check_target_authority(actor, target)
    if target.status != "suspended":
        raise HTTPException(status_code=409, detail="Only suspended members can be reinstated")

    target.status = "active"
    target.suspended_until = None
    record_audit_event(
        db,
        business_id=business_id,
        actor_user_id=actor.user_id,
        event_type="membership.reinstated",
        target_type="business_membership",
        target_id=target.id,
        reason=payload.reason,
    )
    db.commit()
    db.refresh(target)
    user = db.get(User, target.user_id)
    assert user is not None
    return {
        "membership_id": target.id,
        "user_id": target.user_id,
        "email": user.email,
        "role": target.role,
        "status": target.status,
        "permissions": target.permissions or {},
        "created_at": target.created_at,
        "suspended_until": target.suspended_until,
        "revoked_at": target.revoked_at,
    }


@router.post("/leave", response_model=MembershipLeaveResponse)
def leave_workspace(
    business_id: UUID,
    payload: MembershipLeaveRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MembershipLeaveResponse:
    """Leave a business after exact-phrase confirmation and password re-authentication."""
    _ensure_business_workspace(db, business_id)
    membership = db.scalar(
        select(BusinessMembership).where(
            BusinessMembership.business_id == business_id,
            BusinessMembership.user_id == user.id,
        )
    )
    if membership is None or membership.status == "revoked":
        raise HTTPException(status_code=404, detail="Business membership not found")
    if membership.role == "owner":
        raise HTTPException(
            status_code=409,
            detail="Workspace ownership must be transferred before the owner can leave",
        )
    if membership.leave_effective_at is not None:
        raise HTTPException(status_code=409, detail="A departure is already scheduled")
    if payload.confirmation_phrase != "I want to leave":
        raise HTTPException(status_code=422, detail='Type the exact phrase "I want to leave"')
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Password confirmation failed")

    now = datetime.now(UTC)
    membership.leave_reason = payload.reason
    if payload.notice_hours is not None:
        membership.leave_effective_at = now + timedelta(hours=payload.notice_hours)
        event_type = "membership.leave_scheduled"
        response_status = "scheduled"
        message = "Your departure is scheduled. Workspace access follows your current membership state until the effective time."
    else:
        membership.leave_effective_at = now
        membership.status = "revoked"
        membership.revoked_at = now
        membership.suspended_until = None
        event_type = "membership.left"
        response_status = "revoked"
        message = "You have left the workspace. Historical financial records are preserved."

    record_audit_event(
        db,
        business_id=business_id,
        actor_user_id=user.id,
        event_type=event_type,
        target_type="business_membership",
        target_id=membership.id,
        reason=payload.reason,
        metadata={"notice_hours": payload.notice_hours},
    )
    db.commit()
    return MembershipLeaveResponse(
        status=response_status,
        effective_at=membership.leave_effective_at,
        message=message,
    )


@router.get("/audit-events", response_model=list[AuditEventRead])
def list_audit_events(
    business_id: UUID,
    actor: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditEvent]:
    """Return read-only audit history to authorized workspace administrators."""
    require_permission(actor, "staff_administration", "read")
    _ensure_business_workspace(db, business_id)
    query = (
        select(AuditEvent)
        .where(AuditEvent.business_id == business_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(query).all())
