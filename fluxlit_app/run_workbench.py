from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Callable, cast

from fluxlit.runtime import find_free_port, run_unified

here = Path(__file__).resolve()
app_root = here.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _enable_debug_defaults() -> None:
    """Turn on the useful frontend, backend, and proxy diagnostics together."""

    os.environ.setdefault("DEBUG", "1")
    os.environ.setdefault("LOG_LEVEL", "debug")
    os.environ.setdefault("FLUXLIT_DEBUG", "1")
    os.environ.setdefault("FLUXLIT_LOG_LEVEL", "debug")
    os.environ.setdefault("FLUXLIT_TRACE_LOGGING", "1")


def _run_migrations_if_enabled() -> None:
    val = (os.environ.get("RUN_MIGRATIONS") or "").strip()
    if val and not _truthy(val):
        return
    subprocess.check_call(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=app_root,
        env=os.environ.copy(),
    )


def _env_int(name: str) -> int | None:
    raw = (os.environ.get(name) or "").strip()
    return int(raw) if raw else None


def _gateway_port() -> int:
    return _env_int("PORT") or _env_int("FLUXLIT_GATEWAY_PORT") or find_free_port()


def _browser_url(host: str, port: int) -> str:
    browser_host = "127.0.0.1" if host in {"", "0.0.0.0", "::"} else host
    root = (os.environ.get("FLUXLIT_ROOT_PATH") or "").strip().rstrip("/")
    return (
        f"http://{browser_host}:{port}{root}/"
        if root
        else f"http://{browser_host}:{port}/"
    )


def _public_base_url(host: str, port: int) -> str:
    return _browser_url(host, port).rstrip("/")


def start_app(
    *,
    app_module_name: str = "main",
    app_variable_name: str = "app",
    open_with_browser: bool = True,
    debug: bool | None = None,
) -> None:
    """
    Start the combined FluxLit app in Posit Workbench-friendly mode.
    """

    if debug is None:
        debug = _truthy(os.environ.get("FLUXLIT_WORKBENCH_DEBUG")) or _truthy(
            os.environ.get("DEBUG")
        )
    if debug:
        _enable_debug_defaults()

    os.environ.setdefault("FLUXLIT_TRUST_PROXY", "1")
    base_path = (os.environ.get("BASE_PATH") or "").strip()
    if base_path:
        os.environ.setdefault("FLUXLIT_ROOT_PATH", base_path.rstrip("/"))

    host = (
        os.environ.get("HOST") or os.environ.get("FLUXLIT_GATEWAY_HOST") or "127.0.0.1"
    )
    port = _gateway_port()
    os.environ.setdefault("PORT", str(port))
    os.environ.setdefault("FLUXLIT_GATEWAY_PORT", str(port))
    os.environ.setdefault("FLUXLIT_PUBLIC_BASE_URL", _public_base_url(host, port))
    log_level = (
        os.environ.get("LOG_LEVEL") or os.environ.get("FLUXLIT_LOG_LEVEL") or "info"
    )
    target = f"{app_module_name}:{app_variable_name}"

    _run_migrations_if_enabled()
    if open_with_browser:
        webbrowser.open(_browser_url(host, port))

    run_workbench_unified = cast(Callable[..., None], run_unified)
    run_workbench_unified(
        target,
        host=host,
        port=port,
        log_level=log_level,
        workbench_mode=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the FluxLit app in Posit Workbench-friendly mode."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable frontend, backend, FluxLit, Uvicorn, and Workbench debug logs.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the app/docs URL in a browser.",
    )
    args = parser.parse_args()
    start_app(open_with_browser=not args.no_browser, debug=args.debug or None)
