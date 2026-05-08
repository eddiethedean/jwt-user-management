from __future__ import annotations

from pathlib import Path

from app.main import app as fastapi_app
from fastapi.responses import PlainTextResponse
from fastapi_workbench import workbenchify


class _StripPrefixASGI:
    """
    Starlette's `Mount` keeps `scope['path']` intact and relies on `root_path`.
    Streamlit's ASGI adapter expects to run at the root of its scope and will
    redirect if it sees the mount prefix in `path`.

    This wrapper strips the mount prefix from `scope['path']` before passing the
    request to Streamlit, while keeping `root_path` as provided by the mount.
    """

    def __init__(self, app, *, prefix: str) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/") or "/"

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if not isinstance(path, str):
            await self.app(scope, receive, send)
            return

        prefix = self.prefix
        if path == prefix:
            new_path = "/"
        elif path.startswith(prefix + "/"):
            new_path = path[len(prefix) :] or "/"
        else:
            new_path = path

        if new_path == path:
            await self.app(scope, receive, send)
            return

        new_scope = dict(scope)
        new_scope["path"] = new_path
        # raw_path is optional but helps consistency for downstream frameworks.
        if isinstance(scope.get("raw_path"), (bytes, bytearray)):
            new_scope["raw_path"] = new_path.encode()
        await self.app(new_scope, receive, send)


try:
    # Streamlit >= 1.53 provides an experimental ASGI entry point.
    # This lets us serve the Streamlit UI from the same FastAPI process.
    from streamlit.starlette import App as StreamlitApp  # type: ignore[import-not-found]

    _repo_root = Path(__file__).resolve().parents[2]
    _streamlit_script = _repo_root / "streamlit_user" / "user_app.py"
    _st = StreamlitApp(str(_streamlit_script))
    fastapi_app.mount("/app", _StripPrefixASGI(_st, prefix="/app"))
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
