"""ASGI entrypoint for running FluxLit behind Posit Workbench-style proxies."""

from __future__ import annotations

import sys
from pathlib import Path


_here = Path(__file__).resolve()
_fastapi_workbench_src = str(_here.parents[1] / "fastapi_workbench" / "src")
if _fastapi_workbench_src not in sys.path:
    sys.path.insert(0, _fastapi_workbench_src)

from fastapi_workbench import workbenchify  # type: ignore[import-not-found]  # noqa: E402
from main import app as fluxlit_app  # noqa: E402


app = workbenchify(fluxlit_app)

__all__ = ["app"]
