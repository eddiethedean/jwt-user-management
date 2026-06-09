from __future__ import annotations

import pytest

import app.core.config as config_mod
from app.core.config import Settings


def test_settings_rejects_invalid_directory_profile(monkeypatch) -> None:
    monkeypatch.setattr(config_mod._defaults, "DIRECTORY_ATTRIBUTE_PROFILE", "invalid")
    with pytest.raises(ValueError, match="DIRECTORY_ATTRIBUTE_PROFILE"):
        Settings()


def test_settings_rejects_invalid_auth_cookie_deployment(monkeypatch) -> None:
    monkeypatch.setattr(config_mod._defaults, "AUTH_COOKIE_DEPLOYMENT", "staging")
    with pytest.raises(ValueError, match="AUTH_COOKIE_DEPLOYMENT"):
        Settings()


def test_settings_rejects_min_password_length_below_one(monkeypatch) -> None:
    monkeypatch.setattr(config_mod._defaults, "MIN_PASSWORD_LENGTH", 0)
    with pytest.raises(ValueError, match="MIN_PASSWORD_LENGTH"):
        Settings()


def test_registration_directory_applies_to_email(monkeypatch) -> None:
    monkeypatch.setattr(
        config_mod._defaults, "REGISTRATION_DIRECTORY_LOOKUP_ENABLED", False
    )
    config_mod.refresh_settings()
    assert (
        config_mod.settings.registration_directory_applies_to_email("a@example.com")
        is False
    )

    monkeypatch.setattr(
        config_mod._defaults, "REGISTRATION_DIRECTORY_LOOKUP_ENABLED", True
    )
    config_mod.refresh_settings()
    # No DIRECTORY_LOOKUP_URL in env during unit test — still false
    assert (
        config_mod.settings.registration_directory_applies_to_email("a@example.com")
        is False
    )


def test_registration_directory_suffix_filter(monkeypatch) -> None:
    monkeypatch.setenv("DIRECTORY_LOOKUP_URL", "http://directory.test/")
    monkeypatch.setattr(
        config_mod._defaults, "REGISTRATION_DIRECTORY_LOOKUP_ENABLED", True
    )
    monkeypatch.setattr(
        config_mod._defaults,
        "REGISTRATION_DIRECTORY_LOOKUP_SUFFIXES",
        ("example.com",),
    )
    config_mod.refresh_settings()
    s = config_mod.settings
    assert s.registration_directory_applies_to_email("user@example.com") is True
    assert s.registration_directory_applies_to_email("user@example.org") is False

    monkeypatch.setattr(
        config_mod._defaults, "REGISTRATION_DIRECTORY_LOOKUP_SUFFIXES", ()
    )
    config_mod.refresh_settings()
    assert (
        config_mod.settings.registration_directory_applies_to_email("user@example.org")
        is True
    )

    monkeypatch.delenv("DIRECTORY_LOOKUP_URL", raising=False)


def test_ui_brand_stack_pills_normalized(monkeypatch) -> None:
    monkeypatch.setattr(
        config_mod._defaults,
        "UI_BRAND_STACK_PILLS",
        (" FastAPI ", "", "JWT", "  "),
    )
    config_mod.refresh_settings()
    assert config_mod.settings.ui_brand_stack_pills == ("FastAPI", "JWT")


def test_normalized_invite_email_domains(monkeypatch) -> None:
    monkeypatch.setattr(
        config_mod._defaults,
        "INVITE_ALLOWED_EMAIL_DOMAINS",
        ("Example.COM", "@corp.org"),
    )
    config_mod.refresh_settings()
    assert config_mod.settings.normalized_invite_email_domains() == frozenset(
        {"example.com", "corp.org"}
    )
