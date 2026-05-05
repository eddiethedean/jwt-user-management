from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

_ROOT = Path(__file__).resolve().parent

# Shared Jinja environment for the server-rendered HTML UI.
templates = Jinja2Templates(directory=str(_ROOT / "templates"))

