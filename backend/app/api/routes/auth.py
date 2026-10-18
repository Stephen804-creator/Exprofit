"""Registration, login, current-user, and logout endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access_tokens import TOKEN_TTL_SECONDS, create_access_token, decode_access_token
from app.api.deps import bearer_scheme, get_current_user
from app.db.session import get_db
from app.models import AuthSession, Business, BusinessMembership, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


def _new_session(db: Session, user: User) -> TokenResponse:
    """Persist a revocable session before returning its signed token."""
    session_id = uuid4()
    token = create_access_token(user.id, session_id)
    db.add(
        AuthSession(
            id=session_id,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS),
        )
    )
    db.commit()
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Create an account, initial NGN workspace, owner membership, and session."""
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    try:
        db.add(user)
        db.flush()
        business = Business(
            name=payload.business_name,
            currency_code="NGN",
            timezone="Africa/Lagos",
        )
        db.add(business)
        db.flush()
        db.add(BusinessMembership(user_id=user.id, business_id=business.id, role="owner"))
        db.flush()
        session_id = uuid4()
        token = create_access_token(user.id, session_id)
        db.add(
            AuthSession(
                id=session_id,
                user_id=user.id,
                expires_at=datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS),
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate using a generic error that does not disclose account existence."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return _new_session(db, user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create access session") from exc


@router.get("/me", response_model=UserRead)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Return the current identity without exposing the stored password hash."""
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Revoke the current session so its token can no longer be used."""
    try:
        token_user_id, session_id = decode_access_token(credentials.credentials)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    if token_user_id != user.id:
        raise HTTPException(status_code=401, detail="Invalid access token")
    session = db.get(AuthSession, session_id)
    if session is not None and session.user_id == user.id and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
