def test_user_flow_route_and_tunnel(client_factory, monkeypatch):
    client, _ = client_factory()

    create_route = client.post(
        "/api/routes",
        json={
            "domains": ["flow.example.com"],
            "upstream": {"scheme": "http", "host": "127.0.0.1", "port": 8080},
        },
    )
    if create_route.status_code == 200:
        route_id = create_route.json()["id"]
        assert route_id
    else:
        assert create_route.status_code == 409

    async def fake_set_token(token: str):
        assert token == "token-123"
        return {"status": "saved"}

    async def fake_status():
        return {
            "configured": True,
            "token_configured": True,
            "tunnels": [{"id": "tun-1", "name": "main", "status": "inactive"}],
            "vpn": {"status": "not_configured"},
        }

    async def fake_start_tunnel(tunnel_id: str, account_id: str = ""):
        assert tunnel_id == "tun-1"
        return {"status": "started", "tunnel_id": tunnel_id, "container": {"status": "running"}}

    monkeypatch.setattr("backend.routers.inbound.inbound_service.set_cloudflare_token", fake_set_token)
    monkeypatch.setattr("backend.routers.inbound.inbound_service.get_cloudflare_status", fake_status)
    monkeypatch.setattr("backend.routers.inbound.inbound_service.start_cloudflare_tunnel", fake_start_tunnel)

    put_token = client.put("/api/inbound/cloudflare/token", json={"token": "token-123"})
    assert put_token.status_code == 200
    assert put_token.json()["status"] == "saved"

    status = client.get("/api/inbound/cloudflare")
    assert status.status_code == 200
    assert status.json()["configured"] is True
    assert status.json()["tunnels"][0]["id"] == "tun-1"

    start = client.post("/api/inbound/cloudflare/tunnels/tun-1/start")
    assert start.status_code == 200
    assert start.json()["status"] == "started"
    assert start.json()["container"]["status"] == "running"


def test_user_flow_vpn(client_factory, monkeypatch):
    client, _ = client_factory()

    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.get_vpn_status",
        lambda: {"status": "ok", "servers": [], "links": []},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.create_vpn_server",
        lambda name="": {"status": "created", "server": {"id": "srv-1", "name": name or "Main"}},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.start_vpn_server",
        lambda server_id: {"status": "running", "server_id": server_id},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.add_vpn_client",
        lambda server_id, name="": {"status": "created", "client": {"id": "cli-1", "name": name, "server_id": server_id}},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.get_vpn_client_config",
        lambda server_id, client_id: {"status": "ok", "server_id": server_id, "client_id": client_id, "config": "[Interface]\n..."},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.create_vpn_link",
        lambda name="", config="": {"status": "created", "link": {"id": "link-1", "name": name, "config": config}},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.start_vpn_link",
        lambda link_id: {"status": "running", "link_id": link_id},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.stop_vpn_link",
        lambda link_id: {"status": "stopped", "link_id": link_id},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.delete_vpn_link",
        lambda link_id: {"status": "deleted", "link_id": link_id},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.stop_vpn_server",
        lambda server_id: {"status": "stopped", "server_id": server_id},
    )
    monkeypatch.setattr(
        "backend.routers.inbound.inbound_service.delete_vpn_server",
        lambda server_id: {"status": "deleted", "server_id": server_id},
    )

    status = client.get("/api/inbound/vpn")
    assert status.status_code == 200
    assert status.json()["status"] == "ok"

    server = client.post("/api/inbound/vpn/servers", json={"name": "Main"})
    assert server.status_code == 200
    server_id = server.json()["server"]["id"]
    assert server_id == "srv-1"

    start_server = client.post(f"/api/inbound/vpn/servers/{server_id}/start")
    assert start_server.status_code == 200
    assert start_server.json()["status"] == "running"

    client_create = client.post(f"/api/inbound/vpn/servers/{server_id}/clients", json={"name": "Alice"})
    assert client_create.status_code == 200
    client_id = client_create.json()["client"]["id"]
    assert client_id == "cli-1"

    client_cfg = client.get(f"/api/inbound/vpn/servers/{server_id}/clients/{client_id}/config")
    assert client_cfg.status_code == 200
    assert client_cfg.json()["status"] == "ok"

    link = client.post("/api/inbound/vpn/links", json={"name": "Office", "config": "[Interface]\n..."})
    assert link.status_code == 200
    link_id = link.json()["link"]["id"]
    assert link_id == "link-1"

    start_link = client.post(f"/api/inbound/vpn/links/{link_id}/start")
    assert start_link.status_code == 200
    assert start_link.json()["status"] == "running"

    stop_link = client.post(f"/api/inbound/vpn/links/{link_id}/stop")
    assert stop_link.status_code == 200
    assert stop_link.json()["status"] == "stopped"

    delete_link = client.delete(f"/api/inbound/vpn/links/{link_id}")
    assert delete_link.status_code == 200
    assert delete_link.json()["status"] == "deleted"

    stop_server = client.post(f"/api/inbound/vpn/servers/{server_id}/stop")
    assert stop_server.status_code == 200
    assert stop_server.json()["status"] == "stopped"

    delete_server = client.delete(f"/api/inbound/vpn/servers/{server_id}")
    assert delete_server.status_code == 200
    assert delete_server.json()["status"] == "deleted"
