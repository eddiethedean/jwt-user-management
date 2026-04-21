import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from streamlit.testing.v1 import AppTest

from streamlit_common.auth_state import AuthState

ADMIN_APP_PY = str(Path(__file__).resolve().parent.parent / "app.py")


def prime_admin_session(at: AppTest, *, token: str = "test-token", email: str = "admin@test.local") -> None:
    """Pretend the user already signed in so AppTest can reach the admin dashboard."""
    at.session_state["admin_auth"] = AuthState(access_token=token, email=email)
