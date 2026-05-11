"""Central :class:`~fluxlit.config.FluxlitSettings` for the gateway (env + defaults)."""

from __future__ import annotations

from fluxlit.config import FluxlitSettings


def load_fluxlit_settings() -> FluxlitSettings:
    """Defaults for title and page layout; override with ``FLUXLIT_*`` env vars."""
    return FluxlitSettings(
        title="User Management",
        streamlit_page_config={
            "page_title": "User Management",
            "layout": "centered",
            "initial_sidebar_state": "expanded",
        },
    )
