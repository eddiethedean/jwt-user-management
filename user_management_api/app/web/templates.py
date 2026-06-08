from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Any, cast

from fastapi.templating import Jinja2Templates

from app.models import User

_ROOT = Path(__file__).resolve().parent

# Shared Jinja environment for the server-rendered HTML UI.
templates = Jinja2Templates(directory=str(_ROOT / "templates"))


def _fmt_dt(value: object) -> str:
    if not isinstance(value, datetime):
        return str(value) if value is not None else ""

    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    s = dt.strftime("%b %d, %Y %H:%M UTC")
    return s.replace(" 0", " ")


def _fmt_date(value: object) -> str:
    if not isinstance(value, datetime):
        return str(value) if value is not None else ""

    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    s = dt.strftime("%b %d, %Y")
    return s.replace(" 0", " ")


templates.env.filters["fmt_dt"] = _fmt_dt
templates.env.filters["fmt_date"] = _fmt_date


def _app_title() -> str:
    from app.core.config import settings

    return settings.app_title


def _brand_tag() -> str:
    from app.core.config import settings

    return settings.brand_tag


def _brand_tag_title() -> str:
    from app.core.config import settings

    return settings.brand_tag_title


def _brand_stack() -> tuple[str, ...]:
    from app.core.config import settings

    return settings.brand_stack


def _configured_user_roles() -> tuple[str, ...]:
    from app.core.config import settings

    return settings.user_roles


def _self_registration_enabled() -> bool:
    from app.core.config import settings

    return settings.self_registration_enabled


def _user_role_list(user: User) -> list[str]:
    from app.core.config import settings
    from app.core.roles import display_user_roles

    return display_user_roles(user, settings.user_roles)


_jinja_globals = cast(dict[str, Any], templates.env.globals)
_jinja_globals["app_title"] = _app_title
_jinja_globals["brand_tag"] = _brand_tag
_jinja_globals["brand_tag_title"] = _brand_tag_title
_jinja_globals["brand_stack"] = _brand_stack
_jinja_globals["configured_user_roles"] = _configured_user_roles
_jinja_globals["self_registration_enabled"] = _self_registration_enabled
_jinja_globals["user_role_list"] = _user_role_list
