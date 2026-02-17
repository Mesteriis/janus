def test_plugins_get_put(client_factory):
    client, _ = client_factory()

    resp = client.get("/api/plugins")
    assert resp.status_code == 200
    plugins = resp.json()
    assert "tlsredis" in plugins

    update = client.put("/api/plugins", json={"tlsredis": {"address": "redis:6379"}, "unknown": {"x": 1}})
    assert update.status_code == 200
    result = update.json()
    assert result["tlsredis"]["address"] == "redis:6379"
    assert "unknown" not in result


def test_plugins_put_error(client_factory, monkeypatch):
    client, _ = client_factory()
    from app.services.errors import ServiceError

    def boom(_payload):
        raise ServiceError(500, "boom")

    monkeypatch.setattr("backend.routers.plugins.plugins_service.update_plugins", boom)
    resp = client.put("/api/plugins", json={})
    assert resp.status_code == 500


def test_l4_routes_get_put(client_factory):
    client, _ = client_factory()

    resp = client.get("/api/l4routes")
    assert resp.status_code == 200
    assert resp.json()["l4_routes"] == []

    bad = client.put("/api/l4routes", json={"l4_routes": "not-a-list"})
    assert bad.status_code == 400

    ok = client.put("/api/l4routes", json={"l4_routes": [{"listen": ":22"}]})
    assert ok.status_code == 200
    assert ok.json()["l4_routes"][0]["listen"] == ":22"


def test_l4_routes_put_error(client_factory, monkeypatch):
    client, _ = client_factory()
    from app.services.errors import ServiceError

    def boom(_routes):
        raise ServiceError(500, "boom")

    monkeypatch.setattr("backend.routers.l4.l4_service.update_l4_routes", boom)
    resp = client.put("/api/l4routes", json={"l4_routes": []})
    assert resp.status_code == 500
