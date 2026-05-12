from __future__ import annotations

import os
from collections.abc import Iterator
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def _restore_environ() -> Iterator[None]:
    original = os.environ.copy()
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def _load_run_workbench() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "run_workbench.py"
    spec = spec_from_file_location("fluxlit_run_workbench", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_start_app_debug_enables_diagnostics(monkeypatch) -> None:
    run_workbench = _load_run_workbench()
    run_unified = Mock()
    check_call = Mock()
    open_browser = Mock()
    monkeypatch.setattr(run_workbench, "run_unified", run_unified)
    monkeypatch.setattr(run_workbench.subprocess, "check_call", check_call)
    monkeypatch.setattr(run_workbench.webbrowser, "open", open_browser)

    for key in (
        "DEBUG",
        "LOG_LEVEL",
        "FLUXLIT_DEBUG",
        "FLUXLIT_LOG_LEVEL",
        "FLUXLIT_TRACE_LOGGING",
        "FLUXLIT_TRUST_PROXY",
        "BASE_PATH",
        "FLUXLIT_ROOT_PATH",
        "RUN_MIGRATIONS",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("BASE_PATH", "/workbench")
    monkeypatch.setenv("RUN_MIGRATIONS", "0")

    run_workbench.start_app(open_with_browser=False, debug=True)

    assert run_workbench.os.environ["DEBUG"] == "1"
    assert run_workbench.os.environ["LOG_LEVEL"] == "debug"
    assert run_workbench.os.environ["FLUXLIT_DEBUG"] == "1"
    assert run_workbench.os.environ["FLUXLIT_LOG_LEVEL"] == "debug"
    assert run_workbench.os.environ["FLUXLIT_TRACE_LOGGING"] == "1"
    assert run_workbench.os.environ["FLUXLIT_TRUST_PROXY"] == "1"
    assert run_workbench.os.environ["FLUXLIT_ROOT_PATH"] == "/workbench"

    check_call.assert_not_called()
    open_browser.assert_not_called()
    run_unified.assert_called_once_with(
        "main:app",
        host="127.0.0.1",
        port=8000,
        log_level="debug",
        workbench_mode=True,
    )


def test_start_app_uses_debug_env_flag(monkeypatch) -> None:
    run_workbench = _load_run_workbench()
    run_unified = Mock()
    monkeypatch.setattr(run_workbench, "run_unified", run_unified)
    monkeypatch.setattr(run_workbench.subprocess, "check_call", Mock())
    monkeypatch.setattr(run_workbench.webbrowser, "open", Mock())
    monkeypatch.setenv("FLUXLIT_WORKBENCH_DEBUG", "1")
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setenv("RUN_MIGRATIONS", "0")

    run_workbench.start_app(open_with_browser=False)

    assert run_workbench.os.environ["DEBUG"] == "1"
    assert run_workbench.os.environ["FLUXLIT_DEBUG"] == "1"
    run_unified.assert_called_once()
