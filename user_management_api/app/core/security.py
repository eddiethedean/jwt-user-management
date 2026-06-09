from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt
from passlib.context import CryptContext

import app.core.config as app_config


# Use PBKDF2 to avoid platform-specific bcrypt backend issues.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def validate_new_password(password: str) -> None:
    min_len = app_config.settings.min_password_length
    if len(password or "") < min_len:
        raise ValueError(f"Password must be at least {min_len} characters")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def bump_token_version(user: Any) -> None:
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1


def token_extra_claims(user: Any) -> Dict[str, Any]:
    claims: Dict[str, Any] = {"tv": int(getattr(user, "token_version", 0) or 0)}
    country = getattr(user, "country", None)
    if country:
        claims["country"] = country
    return claims


def create_access_token(
    *, subject: str, extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=app_config.settings.jwt_expires_minutes)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        app_config.settings.jwt_secret,
        algorithm=app_config.settings.jwt_algorithm,
    )


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        app_config.settings.jwt_secret,
        algorithms=[app_config.settings.jwt_algorithm],
    )
