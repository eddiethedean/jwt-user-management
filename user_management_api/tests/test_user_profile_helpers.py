from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import cast

import app.core.config as config_mod
from app.models import User
from app.services.directory import DirectoryEmailRecord


def _fake_user(**overrides: object) -> User:
    defaults: dict[str, object] = {
        "id": 1,
        "email": "u@example.com",
        "full_name": None,
        "country": None,
        "command": "Ops",
        "hashed_password": "hashed",
        "is_active": True,
        "is_admin": False,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return cast(User, SimpleNamespace(**defaults))


def test_user_to_api_dict_omits_command_by_default(monkeypatch) -> None:
    monkeypatch.setattr(config_mod._defaults, "USER_COMMAND_FIELD_ENABLED", False)
    config_mod.refresh_settings()
    import app.user_profile as user_profile

    d = user_profile.user_to_api_dict(_fake_user())
    assert "command" not in d


def test_user_to_api_dict_includes_command_when_enabled(monkeypatch) -> None:
    import app.user_profile as user_profile

    monkeypatch.setattr(user_profile, "user_command_field_enabled", lambda: True)
    assert user_profile.user_to_api_dict(_fake_user())["command"] == "Ops"


def test_directory_record_to_lookup_dict_strips_command_when_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(config_mod._defaults, "USER_COMMAND_FIELD_ENABLED", False)
    config_mod.refresh_settings()
    import app.user_profile as user_profile

    rec = DirectoryEmailRecord(
        email="u@example.com",
        display_name="Name",
        country="US",
        command="Ops",
    )
    assert user_profile.directory_record_to_lookup_dict(rec)["command"] == ""


def test_directory_record_to_lookup_dict_includes_command_when_enabled(
    monkeypatch,
) -> None:
    import app.user_profile as user_profile

    monkeypatch.setattr(user_profile, "user_command_field_enabled", lambda: True)

    rec = DirectoryEmailRecord(
        email="u@example.com",
        display_name="Name",
        country="US",
        command="Ops",
    )
    out = user_profile.directory_record_to_lookup_dict(rec)
    assert out["command"] == "Ops"
    assert out["email"] == "u@example.com"
