def test_tunnel_start_requires_token(client_factory):
    client, _ = client_factory(CLOUDFLARE_TUNNEL_TOKEN="")
    resp = client.post("/api/cf/docker/start", json={})
    assert resp.status_code == 400


def test_tunnel_start_stop_status(client_factory, monkeypatch):
    client, _ = client_factory(CLOUDFLARE_TUNNEL_TOKEN="token")

    def fake_start(token):
        return {"status": "started", "token": token}

    def fake_stop():
        return {"status": "stopped"}

    def fake_status():
        return {"status": "running"}

    monkeypatch.setattr("backend.routers.tunnel.tunnel_service.start", fake_start)
    monkeypatch.setattr("backend.routers.tunnel.tunnel_service.stop", fake_stop)
    monkeypatch.setattr("backend.routers.tunnel.tunnel_service.status", fake_status)

    start = client.post("/api/cf/docker/start", json={})
    assert start.status_code == 200
    assert start.json()["status"] == "started"

    status = client.get("/api/cf/docker/status")
    assert status.status_code == 200
    assert status.json()["status"] == "running"

    stop = client.post("/api/cf/docker/stop")
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopped"


def test_tunnel_start_errors(client_factory, monkeypatch):
    client, _ = client_factory(CLOUDFLARE_TUNNEL_TOKEN="token")

    from app.services.errors import ServiceError

    def fake_start(token):
        raise ServiceError(500, "boom")

    monkeypatch.setattr("backend.routers.tunnel.tunnel_service.start", fake_start)
    resp = client.post("/api/cf/docker/start", json={})
    assert resp.status_code == 500


def test_tunnel_stop_status_errors(client_factory, monkeypatch):
    client, _ = client_factory(CLOUDFLARE_TUNNEL_TOKEN="token")

    from app.services.errors import ServiceError

    def boom_stop():
        raise ServiceError(500, "boom")

    def boom_status():
        raise ServiceError(500, "boom")

    monkeypatch.setattr("backend.routers.tunnel.tunnel_service.stop", boom_stop)
    resp = client.post("/api/cf/docker/stop")
    assert resp.status_code == 500

    monkeypatch.setattr("backend.routers.tunnel.tunnel_service.status", boom_status)
    resp2 = client.get("/api/cf/docker/status")
    assert resp2.status_code == 500
