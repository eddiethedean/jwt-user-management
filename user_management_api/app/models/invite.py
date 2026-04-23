from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class InviteToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    full_name: Optional[str] = None
    is_admin: bool = False
    permissions: List[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    token_hash: str = Field(index=True, unique=True)
    invited_by_user_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    used_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class InviteCreate(SQLModel):
    email: str
    full_name: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    is_admin: bool = False
