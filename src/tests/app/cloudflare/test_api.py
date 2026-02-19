import json
import pytest


def test_cf_hostnames_crud_and_apply(client_factory, monkeypatch):
    client, _ = client_factory(CLOUDFLARE_API_TOKEN="token")

    class DummyCF:
        def __init__(self, state_file):
            self.ready = True

        async def bootstrap(self):
            return False

        async def set_token(self, token, persist=True):
            self.ready = True

        async def resolve_zone_for_hostname(self, hostname):
            return {"zone": "example.com", "zone_id": "z", "account_id": "a"}

        async def provision_all_to_caddy(self, **kwargs):
            return {"zone": kwargs.get("zone"), "tunnel_id": "tid"}

    monkeypatch.setattr("backend.cloudflare.hostnames.CloudFlare", DummyCF)

    resp = client.get("/api/cf/hostnames")
    assert resp.status_code == 200
    assert resp.json()["hostnames"] == []

    bad = client.post("/api/cf/hostnames", json={"hostname": "bad host"})
    assert bad.status_code == 400

    empty = client.post("/api/cf/hostnames", json={"hostname": ""})
    assert empty.status_code == 400

    bad_service = client.post("/api/cf/hostnames", json={"hostname": "demo.example.com", "service": "bad"})
    assert bad_service.status_code == 400

    ok = client.post("/api/cf/hostnames", json={"hostname": "demo.example.com", "service": "http://127.0.0.1:80"})
    assert ok.status_code == 200

    # update existing (service + enabled)
    ok2 = client.post("/api/cf/hostnames", json={"hostname": "demo.example.com", "service": "http://127.0.0.1:8080"})
    assert ok2.status_code == 200

    apply_resp = client.post("/api/cf/apply")
    assert apply_resp.status_code == 200

    patch = client.patch(
        "/api/cf/hostnames/demo.example.com",
        json={"service": "http://127.0.0.1:8080", "enabled": False},
    )
    assert patch.status_code == 200

    # invalid service on patch
    bad_patch = client.patch("/api/cf/hostnames/demo.example.com", json={"service": "bad"})
    assert bad_patch.status_code == 400

    # patch not found
    missing = client.patch("/api/cf/hostnames/missing.example.com", json={"enabled": True})
    assert missing.status_code == 404

    delete = client.delete("/api/cf/hostnames/demo.example.com")
    assert delete.status_code == 200

    # delete not found
    delete_missing = client.delete("/api/cf/hostnames/demo.example.com")
    assert delete_missing.status_code == 404


def test_cf_apply_and_sync_require_config(client_factory, monkeypatch):
    client, _ = client_factory(CLOUDFLARE_API_TOKEN="")

    async def _apply():
        return {"status": "ok", "domains": 0}

    async def _sync():
        return {"status": "skipped", "domains": 0, "hostnames_sync": {"added": 0, "updated": 0, "skipped": 0}}

    monkeypatch.setattr("backend.routers.cloudflare.cf_service.apply", _apply)
    monkeypatch.setattr("backend.routers.cloudflare.cf_service.sync_from_routes", _sync)

    apply_resp = client.post("/api/cf/apply")
    assert apply_resp.status_code == 200

    sync_resp = client.post("/api/cf/sync")
    assert sync_resp.status_code == 200


def test_cf_sync_uses_routes(client_factory, monkeypatch):
    client, _ = client_factory(CLOUDFLARE_API_TOKEN="token")
    client.post(
        "/api/routes",
        json={"domains": ["sync.example.com"], "upstream": {"host": "x", "port": 80}},
    )

    from backend.services import cloudflare as cf_service

    monkeypatch.setattr(cf_service, "sync_cf_hostnames_from_routes", lambda _data: {"added": 1, "updated": 0, "skipped": 0})

    async def _sync_flow(data):
        routes = data.get("routes", [])
        domains = sum(len(route.get("domains", [])) for route in routes)
        return {"status": "ok", "domains": domains}

    monkeypatch.setattr(cf_service, "sync_cloudflare_flow", _sync_flow)

    sync_resp = client.post("/api/cf/sync")
    assert sync_resp.status_code == 200
    data = sync_resp.json()
    assert data["status"] == "ok"
    assert data["domains"] == 1
    assert "hostnames_sync" in data


def test_cf_apply_error(client_factory, monkeypatch):
    client, _ = client_factory(CLOUDFLARE_API_TOKEN="token")

    async def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr("backend.services.cloudflare.apply", boom)
    with pytest.raises(RuntimeError):
        client.post("/api/cf/apply")


def test_cf_hostnames_apply_errors_on_crud(client_factory, monkeypatch):
    client, _ = client_factory(CLOUDFLARE_API_TOKEN="token")

    create = client.post(
        "/api/cf/hostnames",
        json={"hostname": "demo.example.com", "service": "http://127.0.0.1:80"},
    )
    assert create.status_code == 200

    patch = client.patch("/api/cf/hostnames/demo.example.com", json={"enabled": False})
    assert patch.status_code == 200

    delete = client.delete("/api/cf/hostnames/demo.example.com")
    assert delete.status_code == 200
