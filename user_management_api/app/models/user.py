from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    email: str = Field(index=True, unique=True)
    full_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    permissions: List[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    email_verified: bool = False
    ad_object_id: Optional[str] = None


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class UserCreate(SQLModel):
    email: str
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_admin: bool = False
    permissions: List[str] = Field(default_factory=list)


class UserUpdate(SQLModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    permissions: Optional[List[str]] = None
    email_verified: Optional[bool] = None
    ad_object_id: Optional[str] = None


class UserPublic(SQLModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    permissions: List[str]
    email_verified: bool
    ad_object_id: Optional[str]
    created_at: datetime
