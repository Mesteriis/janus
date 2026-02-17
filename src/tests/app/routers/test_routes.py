def test_routes_crud_and_conflicts(client_factory):
    client, _ = client_factory()

    resp = client.get("/api/routes")
    assert resp.status_code == 200
    assert resp.json()["routes"] == []

    payload = {
        "domains": ["example.com"],
        "upstream": {"host": "dashboard", "port": 8080},
        "headers_up": [],
        "headers_down": [],
        "response_headers": [],
        "match_headers": [],
        "path_routes": [{"path": "/api", "match_headers": ["X-Path: a"], "upstream": {"host": "x", "port": 80}}],
    }
    create = client.post("/api/routes", json=payload)
    assert create.status_code == 200
    created = create.json()
    assert created["domains"] == ["example.com"]
    assert "id" in created

    # duplicate domains
    dup = client.post("/api/routes", json=payload)
    assert dup.status_code == 409

    # patch: toggle enabled + update domains
    patch = client.patch(f"/api/routes/{created['id']}", json={"enabled": False, "domains": ["api.example.com"]})
    assert patch.status_code == 200
    assert patch.json()["enabled"] is False
    assert patch.json()["domains"] == ["api.example.com"]

    # patch not found
    missing = client.patch("/api/routes/does-not-exist", json={"enabled": True})
    assert missing.status_code == 404

    # replace with conflict
    payload2 = {
        "domains": ["other.example.com"],
        "upstream": {"host": "dashboard", "port": 8080},
        "headers_up": [],
        "headers_down": [],
        "response_headers": [],
        "match_headers": [],
        "path_routes": [],
    }
    create2 = client.post("/api/routes", json=payload2)
    assert create2.status_code == 200
    rid2 = create2.json()["id"]

    payload3 = {
        "domains": ["api.example.com"],  # conflicts with updated first route
        "upstream": {"host": "dashboard", "port": 8080},
        "headers_up": [],
        "headers_down": [],
        "response_headers": [],
        "match_headers": [],
        "path_routes": [],
    }
    conflict = client.put(f"/api/routes/{rid2}", json=payload3)
    assert conflict.status_code == 409

    # successful replace (hit update branch)
    ok_replace = client.put(
        f"/api/routes/{created['id']}",
        json={"domains": ["replace.example.com"], "upstream": {"host": "dashboard", "port": 8080}},
    )
    assert ok_replace.status_code == 200

    # replace not found (no domain conflict)
    payload_missing = dict(payload3)
    payload_missing["domains"] = ["missing.example.com"]
    missing_put = client.put("/api/routes/does-not-exist", json=payload_missing)
    assert missing_put.status_code == 404

    # delete not found
    missing_delete = client.delete("/api/routes/does-not-exist")
    assert missing_delete.status_code == 404

    # delete success
    delete = client.delete(f"/api/routes/{rid2}")
    assert delete.status_code == 200


def test_routes_validation_errors(client_factory):
    client, _ = client_factory()

    # invalid domain
    bad_domain = client.post(
        "/api/routes",
        json={"domains": ["bad host"], "upstream": {"host": "x", "port": 80}},
    )
    assert bad_domain.status_code == 400

    # invalid header line
    bad_header = client.post(
        "/api/routes",
        json={
            "domains": ["example.com"],
            "upstream": {"host": "x", "port": 80},
            "headers_up": ["badheader"],
        },
    )
    assert bad_header.status_code == 400

    # invalid method
    bad_method = client.post(
        "/api/routes",
        json={
            "domains": ["example.com"],
            "upstream": {"host": "x", "port": 80},
            "methods": ["GET", "BAD METHOD"],
        },
    )
    assert bad_method.status_code == 400

    # invalid upstream port
    bad_upstream = client.post(
        "/api/routes",
        json={"domains": ["example.com"], "upstream": {"host": "x", "port": "nope"}},
    )
    assert bad_upstream.status_code == 400


def test_routes_replace_path_header_parsing(client_factory):
    client, _ = client_factory()

    create = client.post(
        "/api/routes",
        json={"domains": ["example.com"], "upstream": {"host": "x", "port": 80}},
    )
    rid = create.json()["id"]

    ok_payload = {
        "domains": ["example.com"],
        "upstream": {"host": "x", "port": 80},
        "path_routes": [
            {"path": "/api", "match_headers": ["X-Path: a"], "upstream": {"host": "x", "port": 80}}
        ],
    }
    ok = client.put(f"/api/routes/{rid}", json=ok_payload)
    assert ok.status_code == 200

    bad_payload = {
        "domains": ["example.com"],
        "upstream": {"host": "x", "port": 80},
        "path_routes": [
            {"path": "/api", "match_headers": ["BadHeader"], "upstream": {"host": "x", "port": 80}}
        ],
    }
    bad = client.put(f"/api/routes/{rid}", json=bad_payload)
    assert bad.status_code == 400
