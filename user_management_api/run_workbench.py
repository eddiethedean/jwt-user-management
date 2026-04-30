from __future__ import annotations

import os
import socket
import subprocess
import webbrowser
from urllib.parse import urlparse

import uvicorn


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


def _get_root_path_for_workbench(port: int) -> str:
    """
    When running under Posit Workbench / RStudio Server, `rserver-url` returns an
    external URL (or URL prefix) for this port.
    """
    return subprocess.run(
        ["/usr/lib/rstudio-server/bin/rserver-url", "-l", str(port)],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()


def start_app(
    *,
    app_module_name: str = "app.asgi",
    app_variable_name: str = "app",
    open_with_browser: bool = True,
) -> None:
    """
    Start the FastAPI app in Posit Workbench-friendly mode.

    - Picks a free ephemeral port (unless PORT is set).
    - If RS_SERVER_URL is set, uses `rserver-url` to infer the external URL/prefix.
    - Runs uvicorn with `root_path` so redirects + docs work under the proxy prefix.
    """
    host = os.environ.get("HOST") or "127.0.0.1"
    port = int(os.environ.get("PORT") or str(_free_port()))

    # Prefer explicit BASE_PATH if provided. Otherwise infer from rserver-url.
    explicit_base_path = (os.environ.get("BASE_PATH") or "").strip()
    root_path = explicit_base_path
    external_url = f"http://{host}:{port}"
    external_base_url = external_url
    external_base_is_full_url = False

    if os.environ.get("RS_SERVER_URL") and not root_path:
        try:
            raw = _get_root_path_for_workbench(port)
            if raw.startswith("http://") or raw.startswith("https://"):
                external_base_url = raw.rstrip("/")
                external_base_is_full_url = True
                parsed = urlparse(external_base_url)
                root_path = parsed.path.rstrip("/")
            else:
                # Some setups may return just the path prefix.
                root_path = raw.rstrip("/")
        except Exception as e:  # noqa: BLE001
            print("Failed to retrieve root_path via rserver-url:", e)

    # If rserver-url returns a full external URL, it already includes the prefix.
    if external_base_is_full_url:
        docs_url = f"{external_base_url}/docs"
    else:
        docs_url = (
            f"{external_url}{root_path}/docs" if root_path else f"{external_url}/docs"
        )

    if open_with_browser:
        try:
            webbrowser.open(docs_url)
        except Exception:
            pass

    uvicorn.run(
        f"{app_module_name}:{app_variable_name}",
        host=host,
        port=port,
        root_path=root_path,
        proxy_headers=True,
        forwarded_allow_ips="*",
        reload=_truthy(os.environ.get("RELOAD"))
        or bool(os.environ.get("RS_SERVER_URL")),
        log_level=os.environ.get("LOG_LEVEL") or "info",
    )


if __name__ == "__main__":
    start_app()
