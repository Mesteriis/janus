import pytest


@pytest.mark.asyncio
async def test_update_plugins(monkeypatch, tmp_path, reload_settings):
    from backend.services import plugins as plugins_service

    monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    reload_settings()

    async def _provision(_data, _trigger):
        return {"status": "ok"}

    monkeypatch.setattr(plugins_service, "provision_after_routes_change", _provision)

    res = await plugins_service.update_plugins({"tlsredis": {"address": "redis:6379"}})
    assert res["tlsredis"]["address"] == "redis:6379"


@pytest.mark.asyncio
async def test_update_l4_routes(monkeypatch, tmp_path, reload_settings):
    from backend.services import l4 as l4_service

    monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    reload_settings()

    async def _provision(_data, _trigger):
        return {"status": "ok"}

    monkeypatch.setattr(l4_service, "provision_after_routes_change", _provision)

    res = await l4_service.update_l4_routes([{"listen": ":22"}])
    assert res["l4_routes"][0]["listen"] == ":22"
