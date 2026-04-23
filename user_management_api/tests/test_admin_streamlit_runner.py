from __future__ import annotations

from app.admin_streamlit import StreamlitAdminRunner


def test_runner_build_env_sets_backend_url_and_pythonpath(tmp_path, monkeypatch):
    runner = StreamlitAdminRunner(repo_root=tmp_path, base_path="admin")
    monkeypatch.setenv("PYTHONPATH", "x")
    env = runner.build_env(backend_url="http://localhost:8000/")
    assert env["BACKEND_URL"] == "http://localhost:8000"
    assert str(tmp_path) in env["PYTHONPATH"]


def test_runner_build_cmd_contains_base_url_path_and_port(tmp_path):
    runner = StreamlitAdminRunner(repo_root=tmp_path, base_path="/admin")
    cmd = runner.build_cmd(port=1234)
    assert "--server.port" in cmd
    assert "1234" in cmd
    assert "--server.baseUrlPath" in cmd
    # baseUrlPath expects no leading slash
    idx = cmd.index("--server.baseUrlPath")
    assert cmd[idx + 1] == "admin"


def test_runner_open_log_falls_back_to_none_when_path_invalid(tmp_path, monkeypatch):
    runner = StreamlitAdminRunner(repo_root=tmp_path)
    # Point log file at a directory so open() fails.
    bad = tmp_path / "dir"
    bad.mkdir()
    monkeypatch.setenv("ADMIN_UI_LOG_FILE", str(bad))
    fp = runner.open_log()
    assert fp is None
