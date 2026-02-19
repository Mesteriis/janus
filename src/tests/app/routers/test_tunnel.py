def test_tunnel_start(client_factory, monkeypatch):
    client, _ = client_factory()

    monkeypatch.setattr("backend.routers.tunnel.tunnel_service.start", lambda token=None: {"status": "running", "token": token})

    resp = client.post("/api/cf/docker/start", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_tunnel_status(client_factory, monkeypatch):
    client, _ = client_factory()

    monkeypatch.setattr("backend.routers.tunnel.tunnel_service.status", lambda: {"status": "running", "id": "cid"})

    status = client.get("/api/cf/docker/status")
    assert status.status_code == 200
    assert status.json()["status"] == "running"


def test_tunnel_stop(client_factory, monkeypatch):
    client, _ = client_factory()

    monkeypatch.setattr("backend.routers.tunnel.tunnel_service.stop", lambda: {"status": "stopped"})

    stop = client.post("/api/cf/docker/stop")
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopped"
