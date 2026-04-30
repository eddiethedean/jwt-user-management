from __future__ import annotations

from fastapi import FastAPI, Request

from fastapi_workbench import workbenchify


_app = FastAPI()


@_app.get("/ping")
def ping() -> dict:
    return {"ok": True}


@_app.get("/scope")
def scope_dump(request: Request) -> dict:
    s = request.scope
    return {"root_path": str(s.get("root_path") or ""), "path": str(s.get("path") or "")}


# This is what we run under uvicorn in integration tests.
app = workbenchify(_app)  # type: ignore[assignment]

