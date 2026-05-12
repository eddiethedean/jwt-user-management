from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


here = Path(__file__).resolve()

# Prefer the in-repo fastapi_workbench package when running from this checkout.
fastapi_workbench_src = str(here.parents[1] / "fastapi_workbench" / "src")
if fastapi_workbench_src not in sys.path:
    sys.path.insert(0, fastapi_workbench_src)

from fastapi_workbench import start_app as _start_app  # type: ignore[import-not-found]  # noqa: E402


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _enable_debug_defaults() -> None:
    """Turn on the useful frontend, backend, and proxy diagnostics together."""

    os.environ.setdefault("DEBUG", "1")
    os.environ.setdefault("WORKBENCH_DEBUG", "1")
    os.environ.setdefault("LOG_LEVEL", "debug")
    os.environ.setdefault("FLUXLIT_TRACE_LOGGING", "1")
    os.environ.setdefault("FLUXLIT_ENABLE_REQUEST_LOGGING", "1")
    os.environ.setdefault("FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG", "1")
    os.environ.setdefault("FLUXLIT_STREAMLIT_PROPAGATE_REQUEST_ID", "1")


def start_app(
    *,
    app_module_name: str = "workbench_app",
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

    _start_app(
        app_module_name=app_module_name,
        app_variable_name=app_variable_name,
        open_with_browser=open_with_browser,
        migrations_cwd=str(here.parent),
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
