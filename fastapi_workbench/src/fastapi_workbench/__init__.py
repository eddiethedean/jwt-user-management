from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .detect import is_workbench_env, is_workbench_request
from .middleware import WorkbenchPathMiddleware, workbenchify
from .redirects import safe_external_redirect, safe_redirect
from .runner import start_app
from .urls import (
    base_path,
    browser_app_mount_path,
    external_base,
    external_ui_url,
    external_url,
    external_workbench_url,
    merge_public_base_with_mount,
    workbench_browser_base,
)

try:
    __version__ = version("fastapi-workbench")
except PackageNotFoundError:  # pragma: no cover — editable run without metadata
    __version__ = "0.3.1"

__all__ = [
    "__version__",
    "WorkbenchPathMiddleware",
    "base_path",
    "browser_app_mount_path",
    "external_base",
    "external_ui_url",
    "external_url",
    "external_workbench_url",
    "merge_public_base_with_mount",
    "workbench_browser_base",
    "is_workbench_env",
    "is_workbench_request",
    "safe_external_redirect",
    "safe_redirect",
    "start_app",
    "workbenchify",
]
