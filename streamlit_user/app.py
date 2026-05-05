"""
Compatibility entrypoint for local running:

    streamlit run app.py

The test suite targets `user_app.py` to avoid importing a module named `app`,
which can conflict with the backend's `user_management_api/app` package during
`pytest` runs.
"""

from streamlit_user.user_app import *  # noqa: F403
