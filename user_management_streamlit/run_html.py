"""Run the legacy HTML UI (see ``html_app.py``)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

_REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    repo = str(_REPO_ROOT)
    if repo not in sys.path:
        sys.path.insert(0, repo)
    host = os.getenv("HTML_HOST", "127.0.0.1")
    port = int(os.getenv("HTML_PORT", "8503"))
    uvicorn.run(
        "user_management_streamlit.html_app:app",
        host=host,
        port=port,
        reload=os.getenv("HTML_RELOAD", "1").lower() in ("1", "true", "yes"),
    )


if __name__ == "__main__":
    main()
