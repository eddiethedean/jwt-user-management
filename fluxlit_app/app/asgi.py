from __future__ import annotations

from app.main import app as fastapi_app
from fastapi.responses import PlainTextResponse
from fastapi_workbench import workbenchify


@fastapi_app.get("/app", include_in_schema=False)
async def _streamlit_legacy_mount_unavailable() -> PlainTextResponse:
    """``/app`` was used for an in-process Streamlit mount; the FluxLit gateway serves the UI."""
    return PlainTextResponse(
        "The legacy /app Streamlit mount is not used here. "
        "Run the FluxLit combined app (see fluxlit_app README) for the browser UI.\n",
        status_code=503,
    )


# ASGI entrypoint used by ``run_workbench.py`` when this package is run standalone.
app = workbenchify(fastapi_app)
