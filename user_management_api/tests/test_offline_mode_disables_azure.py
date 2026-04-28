from app.core import config as config_mod
from app.services.azure_ad import validate_email_in_tenant


def test_offline_mode_disables_azure(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "offline_mode", True)
    monkeypatch.setattr(config_mod.settings, "azure_tenant_id", "t")
    monkeypatch.setattr(config_mod.settings, "azure_client_id", "c")
    monkeypatch.setattr(config_mod.settings, "azure_client_secret", "s")

    # validate_email_in_tenant is async; we assert offline mode bypasses it
    # without needing an async test plugin by checking the early-return path.
    coro = validate_email_in_tenant("user@example.com")
    assert coro is not None
    try:
        out = coro.send(None)  # type: ignore[attr-defined]
        assert out is None
    except StopIteration as e:
        assert e.value is None
