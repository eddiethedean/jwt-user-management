from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from starlette.types import ASGIApp, Scope

ScopeMapping = MutableMapping[str, Any]
Headers = Mapping[str, str]

__all__ = ["ASGIApp", "Scope", "ScopeMapping", "Headers"]
