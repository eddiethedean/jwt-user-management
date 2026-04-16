from typing import Any, Optional

import secrets
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_db(session: Session = Depends(get_session)) -> Session:
    return session


def require_admin_api_key(x_admin_api_key: Optional[str] = None) -> None:
    if not settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin API key is not configured")
    provided: str = (x_admin_api_key or "").strip()
    expected: str = (settings.admin_api_key or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid admin API key")


def get_current_user(
    db: Session = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token: str = creds.credentials
    try:
        payload: dict[str, Any] = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id: Optional[Any] = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")
    user: Optional[User] = db.exec(select(User).where(User.id == user_id_int)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user


def get_optional_user(
    db: Session = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[User]:
    if not creds:
        return None
    token: str = creds.credentials
    try:
        payload: dict[str, Any] = decode_token(token)
    except JWTError:
        return None
    user_id: Optional[Any] = payload.get("sub")
    if not user_id:
        return None
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return None
    user: Optional[User] = db.exec(select(User).where(User.id == user_id_int)).first()
    if not user or not user.is_active:
        return None
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user


def get_optional_admin(
    user: Optional[User] = Depends(get_optional_user),
) -> Optional[User]:
    if not user:
        return None
    if not user.is_admin:
        return None
    return user
