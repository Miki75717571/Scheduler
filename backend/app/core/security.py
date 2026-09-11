import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_access_secret, algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_refresh_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.jwt_access_secret, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.jwt_refresh_secret, algorithms=["HS256"])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("not a refresh token")
    return payload


def hash_invitation_token(raw_token: str) -> str:
    """HMAC the raw token with a server-side secret before persisting/comparing it.

    Only this hash is ever stored (Invitation.token_hash); the raw token exists
    only in the emailed link, so a DB leak alone can't be used to accept invites.
    """
    assert settings.invitation_token_secret is not None  # guaranteed by get_settings()
    return hmac.new(
        settings.invitation_token_secret.encode(), raw_token.encode(), hashlib.sha256
    ).hexdigest()


def generate_invitation_token() -> tuple[str, str]:
    """Return (raw_token, token_hash): the raw token goes in the email link, the hash in the DB."""
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_invitation_token(raw_token)
