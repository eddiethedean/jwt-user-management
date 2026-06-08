from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from fastapi.templating import Jinja2Templates

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


def _user_role_list(user: object) -> list[str]:
    from app.core.config import settings
    from app.core.roles import display_user_roles

    return display_user_roles(user, settings.user_roles)  # type: ignore[arg-type]


templates.env.globals["app_title"] = _app_title
templates.env.globals["brand_tag"] = _brand_tag
templates.env.globals["brand_tag_title"] = _brand_tag_title
templates.env.globals["brand_stack"] = _brand_stack
templates.env.globals["configured_user_roles"] = _configured_user_roles
templates.env.globals["user_role_list"] = _user_role_list
