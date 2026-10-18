"""Workspace endpoints with server-side membership checks."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Business, BusinessMembership, User
from app.schemas.businesses import BusinessCreate, BusinessRead

router = APIRouter(prefix="/businesses", tags=["workspaces"])


@router.get("", response_model=list[BusinessRead])
def list_businesses(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Business]:
    """List only workspaces explicitly assigned to the current account."""
    query = (
        select(Business)
        .join(BusinessMembership, BusinessMembership.business_id == Business.id)
        .where(
            BusinessMembership.user_id == user.id,
            BusinessMembership.status == "active",
        )
        .order_by(Business.created_at.asc())
    )
    return list(db.scalars(query).all())


@router.post("", response_model=BusinessRead, status_code=status.HTTP_201_CREATED)
def create_business(
    payload: BusinessCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Business:
    """Create a shared business workspace without changing the user's Solo workspace."""
    business = Business(
        name=payload.name,
        display_name=payload.display_name,
        workspace_type="business",
        organization_label=payload.organization_label,
        logo_url=str(payload.logo_url) if payload.logo_url else None,
        currency_code=payload.currency_code,
        timezone=payload.timezone,
    )
    db.add(business)
    db.flush()
    db.add(
        BusinessMembership(
            user_id=user.id,
            business_id=business.id,
            role="owner",
            status="active",
            permissions={},
        )
    )
    db.commit()
    db.refresh(business)
    return business
