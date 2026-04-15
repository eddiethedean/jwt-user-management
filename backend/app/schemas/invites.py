from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InviteCreateResponse(BaseModel):
    ok: bool
    invite_url: str
    expires_at: datetime


class InviteAcceptResponse(BaseModel):
    ok: bool
    email_verified: bool


class InviteAcceptFormResponse(BaseModel):
    ok: bool
    error: Optional[str] = None
