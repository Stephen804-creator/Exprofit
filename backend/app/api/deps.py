"""Dependencies for authentication and business-level authorization."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access_tokens import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models import AuthSession, BusinessMembership, User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Return the active account for a valid, unrevoked access session."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id, session_id = decode_access_token(credentials.credentials)
    except (InvalidTokenError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    auth_session = db.get(AuthSession, session_id)
    now = datetime.now(UTC)
    if (
        auth_session is None
        or auth_session.user_id != user_id
        or auth_session.revoked_at is not None
    ):
        raise HTTPException(status_code=401, detail="Access session is unavailable")

    expiry = auth_session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry <= now:
        raise HTTPException(status_code=401, detail="Access session has expired")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    return user


def require_business_membership(
    business_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessMembership:
    """Require an active membership without revealing other workspaces."""
    membership = db.scalar(
        select(BusinessMembership).where(
            BusinessMembership.user_id == user.id,
            BusinessMembership.business_id == business_id,
        )
    )
    if membership is None or membership.status != "active":
        raise HTTPException(status_code=404, detail="Business not found")
    return membership
