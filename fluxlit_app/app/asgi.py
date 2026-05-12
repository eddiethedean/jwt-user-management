from __future__ import annotations

from app.main import app as fastapi_app
from fastapi.responses import PlainTextResponse


@fastapi_app.get("/app", include_in_schema=False)
async def _streamlit_legacy_mount_unavailable() -> PlainTextResponse:
    """``/app`` was used for an in-process Streamlit mount; the FluxLit gateway serves the UI."""
    return PlainTextResponse(
        "The legacy /app Streamlit mount is not used here. "
        "Run the FluxLit combined app (see fluxlit_app README) for the browser UI.\n",
        status_code=503,
    )


# Legacy API-only ASGI entrypoint. The supported browser UI is ``main:app``.
app = fastapi_app
