from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    full_name: Optional[str] = Field(default=None)
    hashed_password: str
    is_active: bool = Field(default=True, index=True)
    is_admin: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InviteToken(SQLModel, table=True):
    __tablename__ = "invite_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    token_hash: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    used_at: Optional[datetime] = None
    grant_admin: bool = Field(default=False, index=True)

    @staticmethod
    def new_raw_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    token_hash: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    used_at: Optional[datetime] = None

    @staticmethod
    def new_raw_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
