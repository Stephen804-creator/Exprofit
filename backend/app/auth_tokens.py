"""Signed access-token helpers with enforced expiration."""

from uuid import UUID
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from app.config import get_settings

TOKEN_TTL_SECONDS = 1800

class InvalidTokenError(Exception):
    """The supplied token is invalid or expired."""

def _serializer() -> URLSafeTimedSerializer:
    secret = get_settings().auth_secret_key
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must contain at least 32 bytes")
    return URLSafeTimedSerializer(secret, salt="exprofit-access-v1")

def create_access_token(user_id: UUID) -> str:
    """Create a signed token containing only the user identifier and token type."""
    return _serializer().dumps({"sub": str(user_id), "type": "access"})

def decode_access_token(token: str) -> UUID:
    """Verify signature and maximum age before trusting the subject."""
    try:
        payload = _serializer().loads(token, max_age=TOKEN_TTL_SECONDS)
        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type")
        return UUID(payload["sub"])
    except (BadSignature, SignatureExpired, ValueError, TypeError, AttributeError) as exc:
        raise InvalidTokenError("Invalid or expired access token") from exc
