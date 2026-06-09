from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AdminUpdateUserRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    roles: Optional[list[str]] = Field(default=None)
    command: Optional[str] = None
