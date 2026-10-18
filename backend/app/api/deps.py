"""Dependencies for authentication and business-level authorization."""

from typing import Annotated
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth_tokens import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models import BusinessMembership, User

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    """Return the active account represented by a valid access token."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = decode_access_token(credentials.credentials)
    except (InvalidTokenError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"}) from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is unavailable", headers={"WWW-Authenticate": "Bearer"})
    return user

def require_business_membership(business_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> BusinessMembership:
    """Require explicit membership; 404 avoids leaking workspace existence."""
    membership = db.scalar(select(BusinessMembership).where(BusinessMembership.user_id == user.id, BusinessMembership.business_id == business_id))
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return membership
