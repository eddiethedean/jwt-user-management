from __future__ import annotations

import os
import sys
from pathlib import Path


here = Path(__file__).resolve()

# Prefer the in-repo fastapi_workbench package when running from this checkout.
fastapi_workbench_src = str(here.parents[1] / "fastapi_workbench" / "src")
if fastapi_workbench_src not in sys.path:
    sys.path.insert(0, fastapi_workbench_src)

from fastapi_workbench import start_app as _start_app  # type: ignore[import-not-found]  # noqa: E402


def start_app(
    *,
    app_module_name: str = "workbench_app",
    app_variable_name: str = "app",
    open_with_browser: bool = True,
) -> None:
    """
    Start the combined FluxLit app in Posit Workbench-friendly mode.
    """

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
    start_app()
