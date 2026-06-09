from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt
from passlib.context import CryptContext

import app.core.config as app_config


# Use PBKDF2 to avoid platform-specific bcrypt backend issues.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def min_password_length() -> int:
    return int(app_config.settings.min_password_length)


def validate_new_password(password: str) -> None:
    n = min_password_length()
    if len(password or "") < n:
        raise ValueError(f"Password must be at least {n} characters")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


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
