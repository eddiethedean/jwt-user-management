from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from fastapi.templating import Jinja2Templates

_ROOT = Path(__file__).resolve().parent

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
