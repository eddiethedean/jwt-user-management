from __future__ import annotations

import logging
from collections.abc import Generator

import pytest
from starlette.testclient import TestClient

from app.core import audit, logging as um_logging


@pytest.fixture(autouse=True)
def _reset_logging_configured() -> Generator[None, None, None]:
    um_logging._configured = False
    root = logging.getLogger(um_logging.LOGGER_ROOT)
    root.handlers.clear()
    yield
    um_logging._configured = False
    root.handlers.clear()


def test_audit_auth_success_logged(capsys: pytest.CaptureFixture[str]) -> None:
    um_logging.configure_logging(level="info")
    audit.log_auth_success(
        method="test",
        email="user@example.com",
        user_id=1,
        is_admin=False,
    )
    err = capsys.readouterr().err
    assert "auth_success" in err
    assert "user@example.com" in err


def test_audit_rate_limited_logged(capsys: pytest.CaptureFixture[str]) -> None:
    um_logging.configure_logging(level="info")
    audit.log_rate_limited(scope="password_forgot", ip="127.0.0.1", email="a@b.c")
    err = capsys.readouterr().err
    assert "rate_limited" in err
    assert "password_forgot" in err


def test_login_failure_emits_audit_log(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    um_logging.configure_logging(level="info")
    app_client.post(
        "/login",
        data={"email": "nobody@example.com", "password": "wrong"},
    )
    err = capsys.readouterr().err
    assert "auth_failed" in err
    assert "invalid_credentials" in err


def test_successful_api_token_emits_audit_log(
    app_client: TestClient, capsys: pytest.CaptureFixture[str], db_engine
) -> None:
    from api_test_helpers import seed_user

    um_logging.configure_logging(level="info")
    seed_user(
        db_engine=db_engine,
        email="tok@example.com",
        password="longpassword1",
    )
    app_client.post(
        "/auth/token",
        data={"username": "tok@example.com", "password": "longpassword1"},
    )
    err = capsys.readouterr().err
    assert "auth_success" in err
    assert "api_token" in err
    assert "tok@example.com" in err
