from __future__ import annotations

from app.main import app as fastapi_app
from fastapi_workbench import workbenchify

# ASGI entrypoint used by `run_workbench.py` and `uvicorn app.asgi:app`.
# Streamlit lives in `../user_management_streamlit/` as a separate process; point it at
# this API with `BACKEND_URL` (see that package's README).
app = workbenchify(fastapi_app)
