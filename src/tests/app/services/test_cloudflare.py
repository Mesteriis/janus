import pytest


@pytest.mark.asyncio
async def test_cloudflare_service_list(monkeypatch):
    from app.services import cloudflare as cf_service

    monkeypatch.setattr(cf_service, "load_cf_hostnames", lambda: {"hostnames": [{"hostname": "a"}], "fallback": "x"})
    monkeypatch.setattr(cf_service, "cf_configured", lambda: True)
    res = cf_service.list_hostnames()
    assert res["configured"] is True
    assert res["hostnames"][0]["hostname"] == "a"


@pytest.mark.asyncio
async def test_cloudflare_service_create_update_delete(monkeypatch):
    from app.services import cloudflare as cf_service
    from app.services.errors import ServiceError

    store = {"hostnames": []}

    def _load():
        return {"hostnames": list(store.get("hostnames", [])), "fallback": store.get("fallback")}

    def _save(data):
        store.clear()
        store.update(data)

    async def _apply(_data):
        return {"status": "ok"}

    monkeypatch.setattr(cf_service, "load_cf_hostnames", _load)
    monkeypatch.setattr(cf_service, "save_cf_hostnames", _save)
    monkeypatch.setattr(cf_service, "cf_configured", lambda: True)
    monkeypatch.setattr(cf_service, "apply_cloudflare_config", _apply)

    created = await cf_service.create_or_update_hostname("demo.example.com", "http://x", True)
    assert created["created"] is True

    updated = await cf_service.create_or_update_hostname("demo.example.com", "http://y", False)
    assert updated["created"] is False

    entry = await cf_service.update_hostname("demo.example.com", {"enabled": True, "service": "http://z"})
    assert entry["service"] == "http://z"

    deleted = await cf_service.delete_hostname("demo.example.com")
    assert deleted["status"] == "deleted"

    with pytest.raises(ServiceError):
        await cf_service.delete_hostname("missing")


@pytest.mark.asyncio
async def test_cloudflare_service_apply_sync_errors(monkeypatch):
    from app.services import cloudflare as cf_service
    from app.services.errors import ServiceError

    monkeypatch.setattr(cf_service, "cf_configured", lambda: False)
    with pytest.raises(ServiceError):
        await cf_service.apply()

    monkeypatch.setattr(cf_service, "cf_configured", lambda: True)

    async def boom(_data):
        raise RuntimeError("boom")

    monkeypatch.setattr(cf_service, "load_cf_hostnames", lambda: {"hostnames": []})
    monkeypatch.setattr(cf_service, "apply_cloudflare_config", boom)
    with pytest.raises(ServiceError):
        await cf_service.apply()

    monkeypatch.setattr(cf_service, "cf_configured", lambda: False)
    with pytest.raises(ServiceError):
        cf_service.sync_from_routes()

    monkeypatch.setattr(cf_service, "cf_configured", lambda: True)
    monkeypatch.setattr(cf_service, "sync_cf_hostnames_from_routes", lambda _d: {"added": 1})
    monkeypatch.setattr(cf_service, "load_routes", lambda: {"routes": []})
    assert cf_service.sync_from_routes()["added"] == 1
