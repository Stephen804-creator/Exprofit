"""Business workspace endpoints with server-side membership checks."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Business, BusinessMembership, User
from app.schemas.businesses import BusinessCreate, BusinessRead

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("", response_model=list[BusinessRead])
def list_businesses(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Business]:
    """List only workspaces explicitly assigned to the current account."""
    query = (
        select(Business)
        .join(BusinessMembership, BusinessMembership.business_id == Business.id)
        .where(BusinessMembership.user_id == user.id)
        .order_by(Business.created_at.asc())
    )
    return list(db.scalars(query).all())


@router.post("", response_model=BusinessRead, status_code=status.HTTP_201_CREATED)
def create_business(
    payload: BusinessCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Business:
    """Create another workspace and grant its creator the owner role."""
    business = Business(
        name=payload.name,
        currency_code=payload.currency_code,
        timezone=payload.timezone,
    )
    db.add(business)
    db.flush()
    db.add(BusinessMembership(user_id=user.id, business_id=business.id, role="owner"))
    db.commit()
    db.refresh(business)
    return business
