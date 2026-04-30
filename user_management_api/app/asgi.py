from __future__ import annotations

from app.main import app as fastapi_app
from app.workbench_adapter import WorkbenchPathAdapter

# ASGI entrypoint used by `run_workbench.py`.
app = WorkbenchPathAdapter(fastapi_app)
