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
    find_free_port = Mock(return_value=8768)
    monkeypatch.setattr(run_workbench, "run_unified", run_unified)
    monkeypatch.setattr(run_workbench, "find_free_port", find_free_port)
    monkeypatch.setattr(run_workbench.subprocess, "check_call", check_call)
    monkeypatch.setattr(run_workbench.webbrowser, "open", open_browser)

    for key in (
        "DEBUG",
        "LOG_LEVEL",
        "FLUXLIT_DEBUG",
        "FLUXLIT_LOG_LEVEL",
        "FLUXLIT_TRACE_LOGGING",
        "FLUXLIT_TRUST_PROXY",
        "FLUXLIT_PUBLIC_BASE_URL",
        "PORT",
        "FLUXLIT_GATEWAY_PORT",
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
    assert run_workbench.os.environ["PORT"] == "8768"
    assert run_workbench.os.environ["FLUXLIT_GATEWAY_PORT"] == "8768"
    assert (
        run_workbench.os.environ["FLUXLIT_PUBLIC_BASE_URL"]
        == "http://127.0.0.1:8768/workbench"
    )

    check_call.assert_not_called()
    open_browser.assert_not_called()
    find_free_port.assert_called_once_with()
    run_unified.assert_called_once_with(
        "main:app",
        host="127.0.0.1",
        port=8768,
        log_level="debug",
        workbench_mode=True,
    )


def test_start_app_uses_debug_env_flag(monkeypatch) -> None:
    run_workbench = _load_run_workbench()
    run_unified = Mock()
    monkeypatch.setattr(run_workbench, "run_unified", run_unified)
    monkeypatch.setattr(run_workbench, "find_free_port", Mock(return_value=8769))
    monkeypatch.setattr(run_workbench.subprocess, "check_call", Mock())
    monkeypatch.setattr(run_workbench.webbrowser, "open", Mock())
    monkeypatch.setenv("FLUXLIT_WORKBENCH_DEBUG", "1")
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setenv("RUN_MIGRATIONS", "0")

    run_workbench.start_app(open_with_browser=False)

    assert run_workbench.os.environ["DEBUG"] == "1"
    assert run_workbench.os.environ["FLUXLIT_DEBUG"] == "1"
    run_unified.assert_called_once()


def test_start_app_respects_explicit_port(monkeypatch) -> None:
    run_workbench = _load_run_workbench()
    run_unified = Mock()
    find_free_port = Mock(return_value=8769)
    monkeypatch.setattr(run_workbench, "run_unified", run_unified)
    monkeypatch.setattr(run_workbench, "find_free_port", find_free_port)
    monkeypatch.setattr(run_workbench.subprocess, "check_call", Mock())
    monkeypatch.setattr(run_workbench.webbrowser, "open", Mock())
    monkeypatch.setenv("RUN_MIGRATIONS", "0")
    monkeypatch.setenv("PORT", "9001")

    run_workbench.start_app(open_with_browser=False, debug=False)

    find_free_port.assert_not_called()
    run_unified.assert_called_once_with(
        "main:app",
        host="127.0.0.1",
        port=9001,
        log_level="info",
        workbench_mode=True,
    )
