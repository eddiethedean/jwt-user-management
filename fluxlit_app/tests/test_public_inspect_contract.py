"""Contract tests for public inspect endpoints (FluxLit intentional divergence)."""

from __future__ import annotations

import pytest
from fluxlit.testing import FluxLitTestClient

from fluxlit_test_helpers import load_fluxlit_app, seed_unused_invite


@pytest.fixture
def tc(tmp_path):
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'inspect.db'}")
    return FluxLitTestClient(app)


@pytest.fixture
def db_engine(tc):
    import app.db as db

    return db.engine


def test_invites_inspect_public_with_valid_token_returns_email(tc, db_engine) -> None:
    """Streamlit accept-invite UI needs unauthenticated inspect (token in body)."""
    raw = seed_unused_invite(db_engine=db_engine, email="invitee@example.com")
    r = tc.api_post("/invites/inspect", json={"token": raw})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("email") == "invitee@example.com"


def test_password_inspect_public_with_valid_token_returns_email(tc, db_engine) -> None:
    """Streamlit reset-password UI needs unauthenticated inspect (token in body)."""
    from datetime import datetime, timezone

    from sqlmodel import Session

    from app.models import PasswordResetToken

    raw = PasswordResetToken.new_raw_token()
    now = datetime.now(timezone.utc)
    rec = PasswordResetToken(
        email="reset@example.com",
        token_hash=PasswordResetToken.hash_token(raw),
        created_at=now,
        expires_at=now.replace(year=2099),
        used_at=None,
    )
    with Session(db_engine) as s:
        s.add(rec)
        s.commit()

    r = tc.api_post("/password/inspect", json={"token": raw})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("email") == "reset@example.com"


def test_inspects_are_rate_limited(tc, db_engine, monkeypatch) -> None:
    import app.core.config as config
    from app.core.rate_limit import reset_rate_limits_for_tests

    raw = seed_unused_invite(db_engine=db_engine, email="rate@example.com")
    config.settings.rate_limit_enabled = True
    config.settings.rate_limit_auth_per_minute = 2
    reset_rate_limits_for_tests()

    for _ in range(2):
        r = tc.api_post("/invites/inspect", json={"token": raw})
        assert r.status_code == 200

    r429 = tc.api_post("/invites/inspect", json={"token": raw})
    assert r429.status_code == 429
    reset_rate_limits_for_tests()
