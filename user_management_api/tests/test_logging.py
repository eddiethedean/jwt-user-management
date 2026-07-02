from __future__ import annotations

import logging
from collections.abc import Generator

import pytest
from starlette.testclient import TestClient

from app.core import logging as um_logging
from app.core.config import settings


@pytest.fixture(autouse=True)
def _reset_logging_configured() -> Generator[None, None, None]:
    um_logging._configured = False
    root = logging.getLogger(um_logging.LOGGER_ROOT)
    root.handlers.clear()
    yield
    um_logging._configured = False
    root.handlers.clear()


def test_configure_logging_uses_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")
    um_logging.configure_logging(fallback="info")
    root = logging.getLogger(um_logging.LOGGER_ROOT)
    assert root.level == logging.DEBUG


def test_get_logger_namespaces_module() -> None:
    log = um_logging.get_logger("app.services.email")
    assert log.name == "user_management.app.services.email"


def test_request_logging_middleware_emits_access_log(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    um_logging.configure_logging(level="info")
    r = app_client.get("/login")
    assert r.status_code == 200
    err = capsys.readouterr().err
    assert "GET /login 200" in err


def test_request_logging_skips_static(
    app_client: TestClient,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    um_logging.configure_logging(level="info")
    monkeypatch.setattr(settings, "log_http_requests", True, raising=False)
    app_client.get("/static/site/forms.css")
    err = capsys.readouterr().err
    assert "GET /static/" not in err
