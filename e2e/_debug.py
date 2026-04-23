from __future__ import annotations

from pathlib import Path
from typing import Optional


def dump_page(page, *, name: str) -> Optional[Path]:
    """
    Best-effort helper for debugging E2E selector failures.
    Writes screenshot + HTML into e2e/artifacts/.
    """
    try:
        root = Path(__file__).resolve().parent
        out = root / "artifacts"
        out.mkdir(exist_ok=True)
        png = out / f"{name}.png"
        html = out / f"{name}.html"
        try:
            page.screenshot(path=str(png), full_page=True)
        except Exception:
            pass
        try:
            html.write_text(page.content(), encoding="utf-8")
        except Exception:
            pass
        return png
    except Exception:
        return None
