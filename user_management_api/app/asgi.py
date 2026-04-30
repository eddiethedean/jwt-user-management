from __future__ import annotations

from app.main import app as fastapi_app
from fastapi_workbench import workbenchify

# ASGI entrypoint used by `run_workbench.py`.
app = workbenchify(fastapi_app)
