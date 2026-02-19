from __future__ import annotations


def test_inject_redirect_rules_adds_table_dnat_and_masquerade():
    from backend.services import vpn

    base = (
        "[Interface]\n"
        "PrivateKey = x\n"
        "Address = 10.10.10.2/32\n"
        "DNS = 1.1.1.1\n\n"
        "[Peer]\n"
        "PublicKey = y\n"
        "AllowedIPs = 0.0.0.0/0\n"
    )

    rendered = vpn._inject_redirect_rules(base, iface="jwgtest", caddy_host="172.17.0.5", caddy_port=80)

    assert "Table = off" in rendered
    assert "DNS = 1.1.1.1" not in rendered
    assert "DNAT --to-destination 172.17.0.5:80" in rendered
    assert "POSTROUTING -o eth0 -p tcp -d 172.17.0.5 --dport 80 -j MASQUERADE" in rendered
    assert "ip route replace 10.10.10.0/24 dev jwgtest" in rendered

    rendered2 = vpn._inject_redirect_rules(rendered, iface="jwgtest", caddy_host="172.17.0.5", caddy_port=80)
    assert rendered2.count("Table = off") == 1
    assert rendered2.count("DNAT --to-destination 172.17.0.5:80") == 2
    assert rendered2.count("MASQUERADE") == 2


def test_start_container_uses_bridge_with_udp_port_mapping(monkeypatch):
    from backend.services import vpn

    captured: dict[str, object] = {}

    class FakeContainer:
        id = "cid"
        status = "running"

        def reload(self):
            return None

    class FakeContainers:
        def run(self, **kwargs):
            captured.update(kwargs)
            return FakeContainer()

    class FakeDocker:
        containers = FakeContainers()

    monkeypatch.setattr(vpn, "_docker_client", lambda: FakeDocker())
    monkeypatch.setattr(vpn, "_remove_container", lambda _name: {"status": "not_found"})
    monkeypatch.setattr(vpn, "_render_server_files", lambda _server: None)

    server = {"id": "srv1", "listen_port": 51820}
    info = vpn._start_container(server)

    assert info["status"] == "running"
    assert captured.get("ports") == {"51820/udp": 51820}
    assert captured.get("privileged") is True
    assert captured.get("cap_add") == ["NET_ADMIN", "SYS_MODULE"]
    assert "network_mode" not in captured


def test_create_server_retries_on_port_bind_conflict(monkeypatch):
    from backend.services import vpn
    from backend.services.errors import ServiceError

    state: dict[str, object] = {"version": 1, "servers": []}
    calls = {"start": 0}

    monkeypatch.setattr(vpn, "_load_state", lambda: state)
    monkeypatch.setattr(vpn, "_save_state", lambda _state: None)
    monkeypatch.setattr(vpn, "_generate_keypair", lambda: ("priv", "pub"))
    monkeypatch.setattr(vpn, "_next_free_subnet", lambda _servers: ("10.66.10.0/24", "10.66.10.1/24"))
    monkeypatch.setattr(vpn, "_next_free_port", lambda _servers: 51820)
    monkeypatch.setattr(vpn, "add_client", lambda *_a, **_k: {"id": "client"})

    def fake_start(server_id: str):
        calls["start"] += 1
        if calls["start"] == 1:
            raise ServiceError(500, "address already in use")
        return {"status": "configured", "server_id": server_id}

    monkeypatch.setattr(vpn, "start_server", fake_start)
    monkeypatch.setattr(vpn, "_render_server_files", lambda _server: None)

    result = vpn.create_server("retry")
    assert result["status"] == "configured"
    assert calls["start"] == 2
    server = state["servers"][0]
    assert server["listen_port"] == 51821


def test_is_port_bind_conflict_variants():
    from backend.services import vpn

    assert vpn._is_port_bind_conflict(Exception("address already in use"))
    assert vpn._is_port_bind_conflict(Exception("failed to bind host port"))
    assert vpn._is_port_bind_conflict(Exception("port is already allocated"))
