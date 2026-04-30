from __future__ import annotations

from unittest.mock import Mock

import run_workbench


def test_start_app_local_uses_free_port_and_no_root_path(monkeypatch) -> None:
    uvicorn_run = Mock()
    web_open = Mock()
    check_call = Mock()

    monkeypatch.setattr(run_workbench, "_free_port", lambda: 12345)
    monkeypatch.setattr(run_workbench.uvicorn, "run", uvicorn_run)
    monkeypatch.setattr(run_workbench.webbrowser, "open", web_open)
    monkeypatch.setattr(run_workbench.subprocess, "check_call", check_call)

    monkeypatch.delenv("RS_SERVER_URL", raising=False)
    monkeypatch.delenv("BASE_PATH", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("RELOAD", raising=False)

    run_workbench.start_app(open_with_browser=True)

    web_open.assert_called_once_with("http://127.0.0.1:12345/docs")
    check_call.assert_called_once()
    uvicorn_run.assert_called_once()
    _, kwargs = uvicorn_run.call_args
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 12345
    assert kwargs["root_path"] == ""


def test_start_app_workbench_full_url_sets_root_path_and_docs_url(monkeypatch) -> None:
    uvicorn_run = Mock()
    web_open = Mock()
    check_call = Mock()

    monkeypatch.setattr(run_workbench, "_free_port", lambda: 23456)
    monkeypatch.setattr(
        run_workbench,
        "_get_root_path_for_workbench",
        lambda port: "https://workbench.socom.mil/proxy/23456/s/x/p/y",
    )
    monkeypatch.setattr(run_workbench.uvicorn, "run", uvicorn_run)
    monkeypatch.setattr(run_workbench.webbrowser, "open", web_open)
    monkeypatch.setattr(run_workbench.subprocess, "check_call", check_call)

    monkeypatch.setenv("RS_SERVER_URL", "1")
    monkeypatch.delenv("BASE_PATH", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("RELOAD", raising=False)

    run_workbench.start_app(open_with_browser=True)

    web_open.assert_called_once_with("https://workbench.socom.mil/s/x/p/y/docs")
    check_call.assert_called_once()
    uvicorn_run.assert_called_once()
    _, kwargs = uvicorn_run.call_args
    assert kwargs["port"] == 23456
    assert kwargs["root_path"] == "/s/x/p/y"


def test_start_app_workbench_prefix_only(monkeypatch) -> None:
    uvicorn_run = Mock()
    web_open = Mock()
    check_call = Mock()

    monkeypatch.setattr(run_workbench, "_free_port", lambda: 34567)
    monkeypatch.setattr(
        run_workbench, "_get_root_path_for_workbench", lambda port: "/s/a/p/b"
    )
    monkeypatch.setattr(run_workbench.uvicorn, "run", uvicorn_run)
    monkeypatch.setattr(run_workbench.webbrowser, "open", web_open)
    monkeypatch.setattr(run_workbench.subprocess, "check_call", check_call)

    monkeypatch.setenv("RS_SERVER_URL", "1")
    monkeypatch.delenv("BASE_PATH", raising=False)

    run_workbench.start_app(open_with_browser=True)

    # When rserver-url returns only a prefix, we fall back to the internal base URL.
    web_open.assert_called_once_with("http://127.0.0.1:34567/s/a/p/b/docs")
    check_call.assert_called_once()
    _, kwargs = uvicorn_run.call_args
    assert kwargs["root_path"] == "/s/a/p/b"


def test_start_app_prefers_explicit_base_path(monkeypatch) -> None:
    uvicorn_run = Mock()
    check_call = Mock()

    monkeypatch.setattr(run_workbench, "_free_port", lambda: 45678)
    monkeypatch.setattr(run_workbench.uvicorn, "run", uvicorn_run)
    monkeypatch.setattr(run_workbench.subprocess, "check_call", check_call)

    monkeypatch.setenv("BASE_PATH", "/explicit/prefix")
    monkeypatch.setenv("RS_SERVER_URL", "1")

    # If BASE_PATH is explicitly set, we won't call rserver-url.
    get_root = Mock(return_value="https://workbench.socom.mil/s/x/p/y")
    monkeypatch.setattr(run_workbench, "_get_root_path_for_workbench", get_root)

    run_workbench.start_app(open_with_browser=False)

    get_root.assert_not_called()
    check_call.assert_called_once()
    _, kwargs = uvicorn_run.call_args
    assert kwargs["root_path"] == "/explicit/prefix"


def test_start_app_can_disable_migrations(monkeypatch) -> None:
    uvicorn_run = Mock()
    check_call = Mock()

    monkeypatch.setattr(run_workbench, "_free_port", lambda: 56789)
    monkeypatch.setattr(run_workbench.uvicorn, "run", uvicorn_run)
    monkeypatch.setattr(run_workbench.subprocess, "check_call", check_call)

    monkeypatch.setenv("RUN_MIGRATIONS", "0")
    monkeypatch.delenv("RS_SERVER_URL", raising=False)
    monkeypatch.delenv("BASE_PATH", raising=False)

    run_workbench.start_app(open_with_browser=False)

    check_call.assert_not_called()
