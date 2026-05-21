"""
Compatibility entrypoint for local running:

    streamlit run app.py

The test suite targets `user_app.py` to avoid importing a module named `app`,
which can conflict with the backend's `user_management_api/app` package during
`pytest` runs.
"""

try:
    # When running from repo root, `user_management_streamlit` is importable as a package.
    from user_management_streamlit.user_app import *  # type: ignore # noqa: F403
except ModuleNotFoundError:
    # When running from inside this directory, Streamlit sets sys.path such
    # that the folder itself is importable, not the package name.
    from user_app import *  # type: ignore # noqa: F403
