from __future__ import annotations

from fastapi.testclient import TestClient

from test_directory_lookup import _load_wrapped_app


def test_register_page_renders_configurable_branding(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'brand.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=False, html_ui_enabled=True)
    import app.core.config as config_mod

    monkeypatch.setattr(config_mod._defaults, "UI_BRAND_TITLE", "Acme Portal")
    monkeypatch.setattr(config_mod._defaults, "UI_BRAND_TAG", "Prod")
    monkeypatch.setattr(
        config_mod._defaults, "UI_BRAND_SUBTITLE", "Internal user access"
    )
    monkeypatch.setattr(
        config_mod._defaults,
        "UI_BRAND_STACK_PILLS",
        ("Python", "Postgres"),
    )
    config_mod.refresh_settings()

    client = TestClient(app)

    r = client.get("/register")
    assert r.status_code == 200
    html = r.text
    assert "Acme Portal" in html
    assert "Prod" in html
    assert "Internal user access" in html
    assert "Python" in html
    assert "Postgres" in html
    assert "FastAPI" not in html


def test_ui_brand_tag_hidden_when_empty(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'brand2.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=False, html_ui_enabled=True)
    import app.core.config as config_mod

    monkeypatch.setattr(config_mod._defaults, "UI_BRAND_TAG", "")
    config_mod.refresh_settings()

    client = TestClient(app)

    r = client.get("/login")
    assert r.status_code == 200
    assert 'class="brandTag"' not in r.text
