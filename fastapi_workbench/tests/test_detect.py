from __future__ import annotations

import pytest
from starlette.requests import Request

from fastapi_workbench.detect import (
    is_workbench_env,
    is_workbench_request,
    is_workbench_scope,
)


def _scope(*, path: str = "/", root_path: str = "") -> dict:
    return {"type": "http", "path": path, "root_path": root_path, "method": "GET"}


def test_is_workbench_scope_encoded_absolute_url() -> None:
    assert is_workbench_scope(_scope(path="/https%3a//host.example/content/app/ping"))


def test_is_workbench_scope_full_root_path_match() -> None:
    assert is_workbench_scope(_scope(path="/content/app", root_path="/content/app"))
    assert is_workbench_scope(
        _scope(path="/content/app/admin", root_path="/content/app")
    )


def test_is_workbench_scope_no_partial_suffix_false_positive() -> None:
    assert not is_workbench_scope(
        _scope(path="/api/ping", root_path="/content/abc/api")
    )


def test_is_workbench_request_true_for_non_empty_root_path() -> None:
    scope = _scope(path="/login", root_path="/api")
    request = Request(scope)
    assert is_workbench_request(request)


def test_is_workbench_request_false_for_rs_server_url_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RS_SERVER_URL", "http://wb")
    monkeypatch.delenv("WORKBENCH_FORCE", raising=False)
    request = Request(_scope(path="/login"))
    assert is_workbench_env()
    assert not is_workbench_request(request)


def test_is_workbench_request_true_for_workbench_force(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RS_SERVER_URL", raising=False)
    monkeypatch.setenv("WORKBENCH_FORCE", "1")
    request = Request(_scope(path="/login"))
    assert is_workbench_request(request)


def test_is_workbench_request_true_when_path_stripped_but_root_path_set() -> None:
    """After middleware, ``path`` is app-relative while ``root_path`` stays mounted."""
    request = Request(_scope(path="/login", root_path="/s/abc/p/proj"))
    assert is_workbench_request(request)


def test_is_workbench_request_true_when_scope_path_partially_stripped() -> None:
    """``path`` may still include mount segments that middleware failed to strip."""
    request = Request(_scope(path="/proj/login", root_path="/s/abc/p/proj"))
    assert is_workbench_request(request)
