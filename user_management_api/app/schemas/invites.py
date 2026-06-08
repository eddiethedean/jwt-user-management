from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateInviteRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    email: str
    grant_admin: bool = False


class InspectInviteRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    token: str


class InviteCreateResponse(BaseModel):
    ok: bool
    invite_url: str
    expires_at: datetime


class InviteAcceptRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    token: str
    password: str
    full_name: Optional[str] = None


class InviteLookupRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    email: str = Field(min_length=1)


class InviteAcceptResponse(BaseModel):
    ok: bool
    email_verified: bool


class InviteAcceptFormResponse(BaseModel):
    ok: bool
    error: Optional[str] = None
