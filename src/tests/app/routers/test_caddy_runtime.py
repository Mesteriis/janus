
def test_caddy_runtime_status_and_logs(client_factory, monkeypatch):
    client, _ = client_factory()

    monkeypatch.setattr(
        "backend.routers.caddy_runtime.runtime_service.get_status",
        lambda include_logs=True: {"state": "running", "include_logs": include_logs},
    )
    monkeypatch.setattr(
        "backend.routers.caddy_runtime.runtime_service.get_logs",
        lambda source="all", limit=200, since_id=0: {"entries": [{"source": source, "id": since_id + 1}], "limit": limit},
    )

    status = client.get("/api/caddy/runtime/status")
    assert status.status_code == 200
    assert status.json()["state"] == "running"

    logs = client.get("/api/caddy/runtime/logs?source=runtime&limit=50")
    assert logs.status_code == 200
    assert logs.json()["entries"][0]["source"] == "runtime"
    assert logs.json()["limit"] == 50


def test_caddy_runtime_actions(client_factory, monkeypatch):
    client, _ = client_factory()

    monkeypatch.setattr(
        "backend.routers.caddy_runtime.runtime_service.start_install",
        lambda addons, reinstall=False: {"status": "started", "addons": addons, "reinstall": reinstall},
    )
    monkeypatch.setattr(
        "backend.routers.caddy_runtime.runtime_service.start_container",
        lambda: {"status": "running"},
    )
    monkeypatch.setattr(
        "backend.routers.caddy_runtime.runtime_service.stop_container",
        lambda: {"status": "stopped"},
    )
    monkeypatch.setattr(
        "backend.routers.caddy_runtime.runtime_service.rollback",
        lambda target_build_id="": {"status": "started", "action": "rollback", "rollback_from": target_build_id or "auto"},
    )

    install = client.post("/api/caddy/runtime/install", json={"addons": ["realip"], "reinstall": True})
    assert install.status_code == 200
    assert install.json()["status"] == "started"
    assert install.json()["reinstall"] is True

    start = client.post("/api/caddy/runtime/start", json={})
    assert start.status_code == 200
    assert start.json()["status"] == "running"

    stop = client.post("/api/caddy/runtime/stop", json={})
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopped"

    rollback = client.post("/api/caddy/runtime/rollback", json={"build_id": "20250101010101"})
    assert rollback.status_code == 200
    assert rollback.json()["action"] == "rollback"


def test_caddy_runtime_service_error(client_factory, monkeypatch):
    client, _ = client_factory()
    from backend.services.errors import ServiceError

    monkeypatch.setattr(
        "backend.routers.caddy_runtime.runtime_service.get_status",
        lambda include_logs=True: (_ for _ in ()).throw(ServiceError(500, "boom")),
    )
    status = client.get("/api/caddy/runtime/status")
    assert status.status_code == 500

    monkeypatch.setattr(
        "backend.routers.caddy_runtime.runtime_service.start_install",
        lambda addons, reinstall=False: (_ for _ in ()).throw(ServiceError(409, "busy")),
    )
    install = client.post("/api/caddy/runtime/install", json={"addons": []})
    assert install.status_code == 409

    monkeypatch.setattr(
        "backend.routers.caddy_runtime.runtime_service.rollback",
        lambda target_build_id="": (_ for _ in ()).throw(ServiceError(404, "not found")),
    )
    rollback = client.post("/api/caddy/runtime/rollback", json={})
    assert rollback.status_code == 404
