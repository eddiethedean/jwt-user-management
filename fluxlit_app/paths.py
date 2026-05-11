"""Path setup and dotenv for the FluxLit app (bundled FastAPI ``app`` package lives here)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_FLUXLIT_APP = Path(__file__).resolve().parent


def ensure_backend_on_path() -> None:
    """Expose the top-level ``app`` package (``fluxlit_app/app/``)."""
    root = str(_FLUXLIT_APP)
    if root not in sys.path:
        sys.path.insert(0, root)


def load_dotenv_files() -> None:
    """Load ``fluxlit_app/.env`` (create from ``.env.example`` if needed)."""
    if os.getenv("FLUXLIT_TESTS") == "1":
        return
    load_dotenv(_FLUXLIT_APP / ".env")
