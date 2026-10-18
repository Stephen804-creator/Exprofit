"""Registration, login, and current-user API endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.auth_tokens import create_access_token
from app.db.session import get_db
from app.models import Business, BusinessMembership, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Create a user and their initial NGN workspace in one transaction."""
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    try:
        db.add(user)
        db.flush()
        business = Business(name=payload.business_name, currency_code="NGN", timezone="Africa/Lagos")
        db.add(business)
        db.flush()
        db.add(BusinessMembership(user_id=user.id, business_id=business.id, role="owner"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    return TokenResponse(access_token=create_access_token(user.id))

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Authenticate with a generic error message to avoid account enumeration."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    return TokenResponse(access_token=create_access_token(user.id))

@router.get("/me", response_model=UserRead)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Return the current authenticated account without exposing its password hash."""
    return user
