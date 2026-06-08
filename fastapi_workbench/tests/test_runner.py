from __future__ import annotations

import pytest

from fastapi_workbench import runner as runner_mod


def test_run_migrations_skipped_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUN_MIGRATIONS", raising=False)
    called: list[str] = []

    def boom(*args, **kwargs):
        called.append("run")
        raise AssertionError("should not run")

    monkeypatch.setattr(runner_mod.subprocess, "check_call", boom)
    runner_mod._run_migrations_if_enabled()
    assert called == []


def test_run_migrations_runs_when_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MIGRATIONS", "true")
    called: list[str] = []

    def ok(*args, **kwargs):
        called.append("run")

    monkeypatch.setattr(runner_mod.subprocess, "check_call", ok)
    runner_mod._run_migrations_if_enabled()
    assert called == ["run"]


def test_parse_port_invalid_returns_none() -> None:
    assert runner_mod._parse_port("8000abc") is None
    assert runner_mod._parse_port("99999") is None


def test_parse_port_valid() -> None:
    assert runner_mod._parse_port("8080") == 8080


def test_start_app_reload_not_tied_to_rs_server_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RS_SERVER_URL", "http://wb")
    monkeypatch.delenv("RELOAD", raising=False)
    monkeypatch.delenv("RUN_MIGRATIONS", raising=False)
    captured: dict = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(runner_mod.uvicorn, "run", fake_run)
    monkeypatch.setattr(
        runner_mod,
        "webbrowser",
        type("W", (), {"open": staticmethod(lambda *_: None)})(),
    )
    runner_mod.start_app(port=18080, open_with_browser=False)
    assert captured.get("reload") is False
