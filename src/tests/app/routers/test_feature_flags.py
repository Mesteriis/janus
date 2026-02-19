def test_features_endpoint_defaults(client_factory):
    client, _ = client_factory()
    resp = client.get("/api/settings/features")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["tunnel_enabled"] is True
    assert payload["vpn_enabled"] is True
    assert payload["inbound_enabled"] is True


def test_runtime_settings_endpoint_and_realtime_update(client_factory):
    client, _ = client_factory()

    runtime = client.get("/api/settings/runtime")
    assert runtime.status_code == 200
    runtime_payload = runtime.json()
    assert runtime_payload["file"]
    assert runtime_payload["features"]["tunnel_enabled"] is True
    assert runtime_payload["features"]["vpn_enabled"] is True

    update_tunnel = client.put("/api/settings/features", json={"tunnel_enabled": False})
    assert update_tunnel.status_code == 200
    payload = update_tunnel.json()
    assert payload["tunnel_enabled"] is False
    assert payload["vpn_enabled"] is True
    assert payload["inbound_enabled"] is True

    # Applied without app restart.
    assert client.get("/api/cf/hostnames").status_code == 404
    assert client.get("/api/inbound/cloudflare").status_code == 404
    assert client.get("/api/inbound/vpn").status_code == 200

    update_vpn = client.put("/api/settings/features", json={"vpn_enabled": False})
    assert update_vpn.status_code == 200
    payload2 = update_vpn.json()
    assert payload2["tunnel_enabled"] is False
    assert payload2["vpn_enabled"] is False
    assert payload2["inbound_enabled"] is False
    assert client.get("/api/inbound/vpn").status_code == 404


def test_tunnel_feature_disabled_hides_related_api(client_factory):
    client, _ = client_factory(FEATURE_TUNNEL_ENABLED="false")

    features = client.get("/api/settings/features")
    assert features.status_code == 200
    payload = features.json()
    assert payload["tunnel_enabled"] is False
    assert payload["vpn_enabled"] is True
    assert payload["inbound_enabled"] is True

    assert client.get("/api/cf/hostnames").status_code == 404
    assert client.get("/api/cf/docker/status").status_code == 404
    assert client.get("/api/inbound/cloudflare").status_code == 404
    assert client.get("/api/inbound/vpn").status_code == 200


def test_vpn_feature_disabled_hides_related_api(client_factory):
    client, _ = client_factory(FEATURE_VPN_ENABLED="false")

    features = client.get("/api/settings/features")
    assert features.status_code == 200
    payload = features.json()
    assert payload["tunnel_enabled"] is True
    assert payload["vpn_enabled"] is False
    assert payload["inbound_enabled"] is True

    assert client.get("/api/inbound/vpn").status_code == 404
    assert client.post("/api/inbound/vpn/servers", json={"name": "x"}).status_code == 404


def test_inbound_feature_disabled_when_both_sources_disabled(client_factory):
    client, _ = client_factory(
        FEATURE_TUNNEL_ENABLED="false",
        FEATURE_VPN_ENABLED="false",
    )

    features = client.get("/api/settings/features")
    assert features.status_code == 200
    payload = features.json()
    assert payload["tunnel_enabled"] is False
    assert payload["vpn_enabled"] is False
    assert payload["inbound_enabled"] is False

    assert client.get("/api/inbound/cloudflare").status_code == 404
    assert client.get("/api/inbound/vpn").status_code == 404
