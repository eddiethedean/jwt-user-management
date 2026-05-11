"""Compatibility entry: same ASGI ``app`` as ``main`` (legacy ``fluxlit_gateway:app`` Uvicorn target)."""

from __future__ import annotations

from main import app

__all__ = ["app"]
