import pytest


@pytest.mark.asyncio
async def test_cloudflare_service_list(monkeypatch):
    from backend.services import cloudflare as cf_service

    monkeypatch.setattr(cf_service, "load_cf_hostnames", lambda: {"hostnames": [{"hostname": "a"}], "fallback": "x"})
    monkeypatch.setattr(cf_service, "cf_configured", lambda: True)
    res = cf_service.list_hostnames()
    assert res["configured"] is True
    assert res["hostnames"][0]["hostname"] == "a"


@pytest.mark.asyncio
async def test_cloudflare_service_create_update_delete(monkeypatch):
    from backend.services import cloudflare as cf_service
    from backend.services.errors import ServiceError

    store = {"hostnames": []}

    def _load():
        return {"hostnames": list(store.get("hostnames", [])), "fallback": store.get("fallback")}

    def _save(data):
        store.clear()
        store.update(data)

    monkeypatch.setattr(cf_service, "load_cf_hostnames", _load)
    monkeypatch.setattr(cf_service, "save_cf_hostnames", _save)
    monkeypatch.setattr(cf_service, "cf_configured", lambda: True)

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
    from backend.services import cloudflare as cf_service

    monkeypatch.setattr(
        cf_service,
        "load_cf_hostnames",
        lambda: {"hostnames": [{"hostname": "demo.example.com", "service": "http://127.0.0.1:80", "enabled": True}]},
    )

    async def _apply(_data):
        return {"status": "ok", "domains": 1}

    monkeypatch.setattr(cf_service, "apply_cloudflare_config", _apply)
    res_apply = await cf_service.apply()
    assert res_apply["status"] == "ok"

    monkeypatch.setattr(cf_service, "sync_cf_hostnames_from_routes", lambda _data: {"added": 1, "updated": 0, "skipped": 0})

    async def _sync_flow(_data):
        return {"status": "ok", "domains": 1}

    monkeypatch.setattr(cf_service, "sync_cloudflare_flow", _sync_flow)
    monkeypatch.setattr(cf_service, "load_routes", lambda: {"routes": [{"domains": ["sync.example.com"]}]})
    res_sync = await cf_service.sync_from_routes()
    assert res_sync["status"] == "ok"
    assert res_sync["hostnames_sync"]["added"] == 1
