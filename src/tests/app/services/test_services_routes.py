import pytest


@pytest.mark.asyncio
async def test_routes_create_replace_update_delete(monkeypatch, tmp_path, reload_settings):
    from backend.services import routes as routes_service

    monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    reload_settings()

    async def _noop(*args, **kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(routes_service, "provision_after_routes_change", _noop)

    payload = {"domains": ["example.com"], "upstreams": [{"scheme": "http", "host": "x", "port": 80, "weight": 1}]}

    created = await routes_service.create_route(dict(payload))
    assert created["domains"] == ["example.com"]

    from backend.services.errors import ServiceError

    # conflict
    with pytest.raises(ServiceError):
        await routes_service.create_route(dict(payload))

    # replace ok
    replaced = await routes_service.replace_route(created["id"], dict(payload))
    assert replaced["id"] == created["id"]

    # replace not found
    with pytest.raises(ServiceError):
        await routes_service.replace_route("missing", dict(payload))

    # update
    updated = await routes_service.update_route(created["id"], {"enabled": False, "domains": ["api.example.com"]})
    assert updated["enabled"] is False
    assert updated["domains"] == ["api.example.com"]

    # update not found
    with pytest.raises(ServiceError):
        await routes_service.update_route("missing", {"enabled": True})

    # delete
    deleted = await routes_service.delete_route(created["id"])
    assert deleted["status"] == "deleted"

    # delete not found
    with pytest.raises(ServiceError):
        await routes_service.delete_route("missing")


@pytest.mark.asyncio
async def test_routes_roll_back_when_provisioning_fails(monkeypatch, tmp_path, reload_settings):
    from backend.services import routes as routes_service
    from backend.services.errors import ServiceError

    monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    reload_settings()

    async def _ok(*args, **kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(routes_service, "provision_after_routes_change", _ok)

    first_payload = {"domains": ["first.example.com"], "upstreams": [{"scheme": "http", "host": "x", "port": 80, "weight": 1}]}
    created = await routes_service.create_route(dict(first_payload))

    async def _boom(*args, **kwargs):
        raise ServiceError(502, "provision failed")

    monkeypatch.setattr(routes_service, "provision_after_routes_change", _boom)

    with pytest.raises(ServiceError):
        await routes_service.create_route(
            {"domains": ["second.example.com"], "upstreams": [{"scheme": "http", "host": "y", "port": 80, "weight": 1}]}
        )
    assert len(routes_service.list_routes().get("routes", [])) == 1

    with pytest.raises(ServiceError):
        await routes_service.update_route(created["id"], {"enabled": False})
    still_created = routes_service.list_routes().get("routes", [])[0]
    assert still_created.get("enabled", True) is True

    with pytest.raises(ServiceError):
        await routes_service.delete_route(created["id"])
    assert len(routes_service.list_routes().get("routes", [])) == 1
