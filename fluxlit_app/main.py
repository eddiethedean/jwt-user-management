"""
ASGI entry: ``FluxLit`` + bundled FastAPI ``app`` + Streamlit UI.

Run from this directory::

    pip install -r requirements.txt
    cp .env.example .env
    alembic upgrade head
    fluxlit dev

See ``fluxlit.toml`` (target ``main:app``) and
https://fluxlit.readthedocs.io/en/stable/configuration.html (``FLUXLIT_*``).
"""

from __future__ import annotations

import sys
from pathlib import Path

# FluxLit loads ``main`` by file path; ensure sibling modules (``paths``, ``api_backend``, …) resolve.
_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from paths import ensure_backend_on_path, load_dotenv_files

ensure_backend_on_path()
load_dotenv_files()

from fluxlit import FluxLit

from api_backend import install_bundled_app_routes
from fluxlit_settings import load_fluxlit_settings
from fluxlit_trace import install_optional_trace_logging

install_optional_trace_logging()

app = FluxLit(
    settings=load_fluxlit_settings(),
    import_target="main:app",
    fastapi_kwargs={"redirect_slashes": False},
)

install_bundled_app_routes(app.api)
app.discover_pages("pages", package="ui")

__all__ = ["app"]
