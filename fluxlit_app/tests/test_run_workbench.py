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
    start_app = Mock()
    monkeypatch.setattr(run_workbench, "_start_app", start_app)

    for key in (
        "DEBUG",
        "WORKBENCH_DEBUG",
        "LOG_LEVEL",
        "FLUXLIT_TRACE_LOGGING",
        "FLUXLIT_ENABLE_REQUEST_LOGGING",
        "FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG",
        "FLUXLIT_STREAMLIT_PROPAGATE_REQUEST_ID",
        "FLUXLIT_TRUST_PROXY",
        "BASE_PATH",
        "FLUXLIT_ROOT_PATH",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("BASE_PATH", "/workbench")

    run_workbench.start_app(open_with_browser=False, debug=True)

    assert run_workbench.os.environ["DEBUG"] == "1"
    assert run_workbench.os.environ["WORKBENCH_DEBUG"] == "1"
    assert run_workbench.os.environ["LOG_LEVEL"] == "debug"
    assert run_workbench.os.environ["FLUXLIT_TRACE_LOGGING"] == "1"
    assert run_workbench.os.environ["FLUXLIT_ENABLE_REQUEST_LOGGING"] == "1"
    assert run_workbench.os.environ["FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG"] == "1"
    assert run_workbench.os.environ["FLUXLIT_STREAMLIT_PROPAGATE_REQUEST_ID"] == "1"
    assert run_workbench.os.environ["FLUXLIT_TRUST_PROXY"] == "1"
    assert run_workbench.os.environ["FLUXLIT_ROOT_PATH"] == "/workbench"

    start_app.assert_called_once_with(
        app_module_name="workbench_app",
        app_variable_name="app",
        open_with_browser=False,
        migrations_cwd=str(Path(__file__).resolve().parents[1]),
    )


def test_start_app_uses_debug_env_flag(monkeypatch) -> None:
    run_workbench = _load_run_workbench()
    start_app = Mock()
    monkeypatch.setattr(run_workbench, "_start_app", start_app)
    monkeypatch.setenv("FLUXLIT_WORKBENCH_DEBUG", "1")
    monkeypatch.delenv("DEBUG", raising=False)

    run_workbench.start_app(open_with_browser=False)

    assert run_workbench.os.environ["DEBUG"] == "1"
    assert run_workbench.os.environ["WORKBENCH_DEBUG"] == "1"
