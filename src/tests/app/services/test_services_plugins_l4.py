import pytest


def test_update_plugins(monkeypatch, tmp_path, reload_settings):
    from app.services import plugins as plugins_service

    monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    reload_settings()

    monkeypatch.setattr(plugins_service, "write_and_validate_config", lambda _d: None)

    res = plugins_service.update_plugins({"tlsredis": {"address": "redis:6379"}})
    assert res["tlsredis"]["address"] == "redis:6379"


def test_update_l4_routes(monkeypatch, tmp_path, reload_settings):
    from app.services import l4 as l4_service

    monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    reload_settings()

    monkeypatch.setattr(l4_service, "write_and_validate_config", lambda _d: None)

    res = l4_service.update_l4_routes([{"listen": ":22"}])
    assert res["l4_routes"][0]["listen"] == ":22"
