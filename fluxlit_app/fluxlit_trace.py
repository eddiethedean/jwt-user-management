"""Optional FluxLit tracing hook (DEBUG logs only; no OpenTelemetry dependency)."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from fluxlit import set_trace_hook


def install_optional_trace_logging() -> None:
    if os.getenv("FLUXLIT_TRACE_LOGGING", "").lower() not in ("1", "true", "yes"):
        return
    log = logging.getLogger("fluxlit.trace")

    @contextmanager
    def _hook(
        name: str, attributes: Mapping[str, str | int | float | bool | None]
    ) -> Iterator[None]:
        log.debug("%s %s", name, dict(attributes))
        yield

    set_trace_hook(_hook)
