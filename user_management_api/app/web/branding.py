from __future__ import annotations

from typing import Any

import app.core.config as app_config


def ui_brand_context() -> dict[str, Any]:
    """Masthead branding for ``base.html`` (reads ``config.py`` at render time)."""
    s = app_config.settings
    return {
        "title": s.ui_brand_title,
        "tag": s.ui_brand_tag,
        "tag_tooltip": s.ui_brand_tag_tooltip,
        "subtitle": s.ui_brand_subtitle,
        "stack_pills": list(s.ui_brand_stack_pills),
    }
