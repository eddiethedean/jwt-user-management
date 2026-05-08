from __future__ import annotations

from pathlib import Path

from app.main import app as fastapi_app
from fastapi.responses import PlainTextResponse
from fastapi_workbench import workbenchify

try:
    # Streamlit >= 1.53 provides an experimental ASGI entry point.
    # This lets us serve the Streamlit UI from the same FastAPI process.
    from streamlit.starlette import App as StreamlitApp  # type: ignore[import-not-found]

    _repo_root = Path(__file__).resolve().parents[2]
    _streamlit_script = _repo_root / "streamlit_user" / "user_app.py"
    fastapi_app.mount("/app", StreamlitApp(str(_streamlit_script)))
except Exception:
    # If Streamlit (or its Starlette extras) isn't installed, we still want the
    # API to start normally. The Streamlit UI will simply be unavailable.
    @fastapi_app.get("/app", include_in_schema=False)
    async def _streamlit_unavailable() -> PlainTextResponse:
        return PlainTextResponse(
            "Streamlit UI is not available in this environment.\n\n"
            "To enable it, install backend dependencies including:\n"
            "  pip install -r user_management_api/requirements.txt\n"
            "which includes streamlit[starlette].\n",
            status_code=503,
        )

# ASGI entrypoint used by `run_workbench.py`.
app = workbenchify(fastapi_app)
