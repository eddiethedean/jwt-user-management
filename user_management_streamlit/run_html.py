"""Run the legacy HTML UI (see ``html_app.py``)."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
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
