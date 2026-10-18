"""Password hashing and bearer-token helpers."""

from pwdlib import PasswordHash

_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Store only an Argon2 password hash."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check a supplied password against its stored hash."""
    try:
        return _password_hasher.verify(password, password_hash)
    except (ValueError, TypeError):
        return False
