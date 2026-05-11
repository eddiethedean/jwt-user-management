"""
ASGI entry: ``FluxLit`` + ``user_management_api`` routes + Streamlit UI.

Run from this directory::

    pip install -r requirements.txt
    cp .env.example .env
    (cd ../user_management_api && alembic upgrade head)
    fluxlit dev

See ``fluxlit.toml`` (target ``main:app``) and
https://fluxlit.readthedocs.io/en/stable/configuration.html (``FLUXLIT_*``).
"""

from __future__ import annotations

from paths import ensure_user_management_on_path, load_dotenv_files

ensure_user_management_on_path()
load_dotenv_files()

from fluxlit import FluxLit

from api_backend import install_user_management_routes
from fluxlit_settings import load_fluxlit_settings
from fluxlit_trace import install_optional_trace_logging

install_optional_trace_logging()

app = FluxLit(
    settings=load_fluxlit_settings(),
    import_target="main:app",
    fastapi_kwargs={"redirect_slashes": False},
)

install_user_management_routes(app.api)
app.discover_pages("pages", package="ui")

__all__ = ["app"]
