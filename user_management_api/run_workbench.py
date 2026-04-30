from __future__ import annotations

import sys

from pathlib import Path

here = Path(__file__).resolve()
# Ensure the fastapi_workbench project root is importable when running from
# `user_management_api/` without an installed wheel.
fastapi_workbench_root = str(here.parents[1] / "fastapi_workbench" / "src")
if fastapi_workbench_root not in sys.path:
    sys.path.insert(0, fastapi_workbench_root)

from fastapi_workbench import start_app as _start_app  # noqa: E402


def start_app(
    *,
    app_module_name: str = "app.asgi",
    app_variable_name: str = "app",
    open_with_browser: bool = True,
) -> None:
    """
    Start the FastAPI app in Posit Workbench-friendly mode.
    """
    _start_app(
        app_module_name=app_module_name,
        app_variable_name=app_variable_name,
        open_with_browser=open_with_browser,
        migrations_cwd=str(here.parent),
    )


if __name__ == "__main__":
    start_app()
