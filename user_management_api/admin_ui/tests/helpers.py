import sys
from pathlib import Path

# ruff: noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_ADMIN_UI_ROOT = Path(__file__).resolve().parents[1]
if str(_ADMIN_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(_ADMIN_UI_ROOT))

from streamlit.testing.v1 import AppTest

from admin_common.auth_state import AuthState

ADMIN_APP_PY = str(Path(__file__).resolve().parents[1] / "app.py")


def prime_admin_session(
    at: AppTest, *, token: str = "test-token", email: str = "admin@test.local"
) -> None:
    """Pretend the user already signed in so AppTest can reach the admin dashboard."""
    at.session_state["admin_auth"] = AuthState(access_token=token, email=email)
