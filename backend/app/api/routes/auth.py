"""Registration, login, current-user, and logout endpoints."""

import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access_tokens import (
    TOKEN_TTL_SECONDS,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
)
from app.api.deps import bearer_scheme, get_current_user
from app.config import get_settings
from app.db.session import get_db
from app.email_delivery import EmailDeliveryError, send_verification_email
from app.models import (
    AuthSession,
    Business,
    BusinessMembership,
    EmailVerificationToken,
    User,
)
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.schemas.email_verification import MessageResponse, VerifyEmailRequest
from app.security import hash_password, verify_password
from app.services.audit import record_audit_event
from app.services.rate_limit import enforce_rate_limit

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
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Create an account, private Solo workspace, owner membership, and session."""
    enforce_rate_limit(
        db,
        request,
        action="auth:register:ip",
        identity="register",
        limit=5,
        window_seconds=3600,
    )
    enforce_rate_limit(
        db,
        request,
        action="auth:register:email",
        identity=str(payload.email),
        limit=3,
        window_seconds=3600,
        include_client_ip=False,
    )
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    try:
        db.add(user)
        db.flush()
        # Preserve the supplied name for compatibility while making the workspace private.
        solo_name = payload.business_name or "My Solo Workspace"
        workspace = Business(
            name=solo_name,
            workspace_type="solo",
            currency_code="NGN",
            timezone="Africa/Lagos",
        )
        db.add(workspace)
        db.flush()
        db.add(
            BusinessMembership(
                user_id=user.id,
                business_id=workspace.id,
                role="owner",
                status="active",
                permissions={},
            )
        )
        db.flush()
        record_audit_event(
            db,
            business_id=workspace.id,
            actor_user_id=user.id,
            event_type="workspace.created",
            target_type="business",
            target_id=workspace.id,
            metadata={"workspace_type": "solo"},
        )
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
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        ) from exc
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate with a generic error that avoids account enumeration."""
    enforce_rate_limit(
        db,
        request,
        action="auth:login:ip",
        identity="login",
        limit=30,
        window_seconds=900,
    )
    enforce_rate_limit(
        db,
        request,
        action="auth:login:email",
        identity=str(payload.email),
        limit=10,
        window_seconds=900,
        include_client_ip=False,
    )
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or not verify_password(
        payload.password, user.password_hash
    ):
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
    """Revoke the current session so its token cannot be reused."""
    try:
        token_user_id, session_id = decode_access_token(credentials.credentials)
    except (InvalidTokenError, RuntimeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    if token_user_id != user.id:
        raise HTTPException(status_code=401, detail="Invalid access token")

    session = db.get(AuthSession, session_id)
    if session is not None and session.user_id == user.id and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/request-email-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_email_verification(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MessageResponse:
    """Email a short-lived verification link to the signed-in account owner."""
    if user.email_verified:
        return MessageResponse(message="If verification is needed, an email will be sent.")

    settings = get_settings()
    if not settings.email_delivery_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email verification delivery is not configured",
        )

    now = datetime.now(UTC)
    previous_tokens = db.scalars(
        select(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.consumed_at.is_(None),
        )
        .with_for_update()
    ).all()
    for previous in previous_tokens:
        previous.consumed_at = now

    raw_token = secrets.token_urlsafe(32)
    token_record = EmailVerificationToken(
        user_id=user.id,
        token_hash=sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=now + timedelta(minutes=settings.email_verification_ttl_minutes),
    )
    db.add(token_record)
    db.commit()

    verification_url = (
        f"{settings.frontend_base_url.rstrip('/')}/verify-email?token={raw_token}"
    )
    try:
        send_verification_email(user.email, verification_url, settings)
    except EmailDeliveryError as exc:
        token_record.consumed_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification email could not be sent. Please try again later.",
        ) from exc

    return MessageResponse(message="If verification is needed, an email will be sent.")


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(
    payload: VerifyEmailRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MessageResponse:
    """Consume a valid single-use challenge and mark the associated email verified."""
    token_hash = sha256(payload.token.encode("utf-8")).hexdigest()
    token_record = db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == token_hash)
        .with_for_update()
    )
    now = datetime.now(UTC)
    if token_record is None or token_record.consumed_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        token_record.consumed_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user = db.get(User, token_record.user_id)
    if user is None or not user.is_active:
        token_record.consumed_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user.email_verified = True
    token_record.consumed_at = now
    other_tokens = db.scalars(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.id != token_record.id,
            EmailVerificationToken.consumed_at.is_(None),
        )
    ).all()
    for other in other_tokens:
        other.consumed_at = now
    db.commit()
    return MessageResponse(message="Email address verified successfully.")
