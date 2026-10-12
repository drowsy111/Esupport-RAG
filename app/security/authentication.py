from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.exceptions import AppError

_hasher = PasswordHasher()
_dummy_hash = _hasher.hash("dummy-login-timing-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        valid = _hasher.verify(hashed or _dummy_hash, password)
        return valid and hashed is not None
    except (VerificationError, ValueError):
        return False


def issue_token(user, settings) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": user.id, "tenant_id": user.tenant_id,
        "iat": now, "exp": now + timedelta(minutes=settings.token_minutes),
        "iss": "enterprise-support-rag", "aud": "rag-api",
    }, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_token(token: str, settings) -> dict:
    try:
        return jwt.decode(
            token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"],
            issuer="enterprise-support-rag", audience="rag-api",
            options={"require": ["exp", "iat", "sub", "tenant_id"]},
        )
    except jwt.InvalidTokenError as exc:
        raise AppError("UNAUTHORIZED", "身份无效或已过期", 401) from exc
