from __future__ import annotations

import sys

from pathlib import Path

from fastapi_workbench import start_app as _start_app


def start_app(
    *,
    app_module_name: str = "app.asgi",
    app_variable_name: str = "app",
    open_with_browser: bool = True,
) -> None:
    """
    Start the FastAPI app in Posit Workbench-friendly mode.
    """
    # Ensure the repo root is importable when running from `user_management_api/`.
    # This allows importing `fastapi_workbench` (top-level package) without requiring
    # a separate pip install step during development.
    here = Path(__file__).resolve()
    repo_root = str(here.parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    _start_app(
        app_module_name=app_module_name,
        app_variable_name=app_variable_name,
        open_with_browser=open_with_browser,
        migrations_cwd=str(here.parent),
    )


if __name__ == "__main__":
    start_app()
