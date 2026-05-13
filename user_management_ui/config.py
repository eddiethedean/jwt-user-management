"""
Streamlit UI defaults that are safe to commit.

The app reads ``BACKEND_URL`` and ``DEBUG`` from ``.env`` (or the process environment)
after loading that file in ``user_app.py``. This module is loaded by path so its
constants are not confused with other packages named ``config``.

- ``DEFAULT_BACKEND_PORT`` and ``DEFAULT_BACKEND_BASE_PATH`` apply only when
  ``BACKEND_URL`` is unset, to build ``http://localhost:{port}{base_path}``.
- ``DEBUG_DEFAULT`` is used when the ``DEBUG`` environment variable is absent
  (set ``DEBUG=1`` / ``true`` in ``.env`` to enable the sidebar debug panel).
"""

# Used when BACKEND_URL is not set: http://localhost:{PORT}{BASE_PATH}
DEFAULT_BACKEND_PORT: str = "8001"
DEFAULT_BACKEND_BASE_PATH: str = ""

# When DEBUG is unset, treat as disabled (set DEBUG=1 in .env to enable).
DEBUG_DEFAULT: bool = False
