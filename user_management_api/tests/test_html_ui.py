from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_repo_root = Path(__file__).resolve().parents[2]
_fw_src = _repo_root / "fastapi_workbench" / "src"
if str(_fw_src) not in sys.path:
    sys.path.insert(0, str(_fw_src))
_fw_tests = _repo_root / "fastapi_workbench" / "tests"
if str(_fw_tests) not in sys.path:
    sys.path.insert(0, str(_fw_tests))

from mock_workbench import MockWorkbenchProxy  # noqa: E402

from test_directory_lookup import _load_wrapped_app, _seed_admin  # noqa: E402


def test_html_ui_workbench_redirects_use_prefix(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RS_SERVER_URL", "http://workbench.test")
    db_url = f"sqlite:///{tmp_path / 'html_wb.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=False)
    prefix = "/s/test/p/proj"
    proxy = MockWorkbenchProxy(upstream=app, external_prefix=prefix)
    client = TestClient(proxy, base_url="http://testserver")

    r = client.get(f"{prefix}/", follow_redirects=False)
    assert r.status_code in (303, 307)
    loc = r.headers.get("location") or ""
    assert "register" in loc

    r = client.get(f"{prefix}/register")
    assert r.status_code == 200
    assert f'action="{prefix}/register"' in r.text

    import app.db as db_mod

    _seed_admin(db_engine=db_mod.engine)
    login = client.post(
        f"{prefix}/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert login.status_code in (303, 307)
    assert login.headers.get("location") == f"{prefix}/admin"


def test_html_ui_pages_available(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'html_on.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=False)
    client = TestClient(app)

    r = client.get("/", follow_redirects=False)
    assert r.status_code in (303, 307)
    assert "/register" in (r.headers.get("location") or "")

    r = client.get("/register")
    assert r.status_code == 200
    assert "email" in r.text.lower()

    r = client.get("/login")
    assert r.status_code == 200

    import app.db as db_mod

    _seed_admin(db_engine=db_mod.engine)
    login = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert login.status_code in (303, 307)
    r = client.get("/users", headers={"accept": "text/html"})
    assert r.status_code == 200
