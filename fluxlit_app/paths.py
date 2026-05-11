"""Repository paths and dotenv loading (import before ``main`` / ``FluxLit``)."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
_USER_MANAGEMENT_API = _REPO_ROOT / "user_management_api"
_FLUXLIT_APP = Path(__file__).resolve().parent


def ensure_user_management_on_path() -> None:
    """Put ``user_management_api`` on ``sys.path`` so ``import app.*`` works."""
    root = str(_USER_MANAGEMENT_API)
    if root not in sys.path:
        sys.path.insert(0, root)


def load_dotenv_files() -> None:
    """Load shared API ``.env`` first, then ``fluxlit_app/.env`` for overrides."""
    load_dotenv(_USER_MANAGEMENT_API / ".env")
    load_dotenv(_FLUXLIT_APP / ".env")
