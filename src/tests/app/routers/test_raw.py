import json
import types


def test_raw_routes_crud_and_validation(client_factory):
    client, _ = client_factory()

    resp = client.get("/api/raw/routes")
    assert resp.status_code == 200
    assert "content" in resp.json()
    content = json.loads(resp.json()["content"])
    assert list(content.keys()) == ["routes"]

    missing_content = client.put("/api/raw/routes", json={})
    assert missing_content.status_code == 400

    empty_content = client.put("/api/raw/routes", json={"content": ""})
    assert empty_content.status_code == 400

    invalid_json = client.put("/api/raw/routes", json={"content": "{"})
    assert invalid_json.status_code == 400

    invalid_shape = client.put("/api/raw/routes", json={"content": json.dumps({"foo": "bar"})})
    assert invalid_shape.status_code == 400

    ok = client.put("/api/raw/routes", json={"content": json.dumps({"routes": []})})
    assert ok.status_code == 200
    assert ok.json()["status"] == "saved"


def test_raw_routes_service_error(client_factory, monkeypatch):
    client, _ = client_factory()
    from app.services.errors import ServiceError

    async def boom(_content, _data):
        raise ServiceError(500, "boom")

    monkeypatch.setattr("backend.routers.raw.raw_service.update_routes_raw", boom)
    resp = client.put("/api/raw/routes", json={"content": json.dumps({"routes": []})})
    assert resp.status_code == 500


def test_raw_config_read_and_create(client_factory):
    client, tmp_path = client_factory()
    config_path = tmp_path / "config.json5"
    assert not config_path.exists()

    resp = client.get("/api/raw/config")
    assert resp.status_code == 200
    assert config_path.exists()

    config_path.write_text("custom")
    resp2 = client.get("/api/raw/config")
    assert resp2.status_code == 200
    assert resp2.json()["content"] == "custom"


def test_convert_caddyfile_and_validate(client_factory, monkeypatch):
    client, _ = client_factory()

    empty = client.post("/api/convert/caddyfile", json={"content": ""})
    assert empty.status_code == 400

    class DummyProc:
        def __init__(self, stdout=b"{}", stderr=b""):
            self.stdout = stdout
            self.stderr = stderr

    def fake_run_ok(*args, **kwargs):
        return DummyProc(stdout=b"{\"ok\":true}")

    def fake_run_fail(*args, **kwargs):
        raise __import__("subprocess").CalledProcessError(1, "caddy", stderr=b"bad caddyfile")

    monkeypatch.setattr("subprocess.run", fake_run_ok)
    ok = client.post("/api/convert/caddyfile", json={"content": "example.com { respond 200 }"})
    assert ok.status_code == 200
    assert "json5" in ok.json()

    monkeypatch.setattr("subprocess.run", fake_run_fail)
    bad = client.post("/api/convert/caddyfile", json={"content": "bad"})
    assert bad.status_code == 400

    # validate config success
    monkeypatch.setattr("subprocess.run", fake_run_ok)
    valid = client.post("/api/validate/config")
    assert valid.status_code == 200

    # validate config failure
    monkeypatch.setattr("subprocess.run", fake_run_fail)
    invalid = client.post("/api/validate/config")
    assert invalid.status_code == 400


def test_convert_caddyfile_missing_caddy(client_factory, monkeypatch):
    client, _ = client_factory()

    def boom(*args, **kwargs):
        raise FileNotFoundError("no caddy")

    monkeypatch.setattr("subprocess.run", boom)
    missing = client.post("/api/convert/caddyfile", json={"content": "example.com { respond 200 }"})
    assert missing.status_code == 503

    missing_validate = client.post("/api/validate/config")
    assert missing_validate.status_code == 503


def test_validate_raw_routes_endpoint(client_factory, monkeypatch):
    client, _ = client_factory()

    missing = client.post("/api/raw/routes/validate", json={})
    assert missing.status_code == 400

    empty = client.post("/api/raw/routes/validate", json={"content": ""})
    assert empty.status_code == 400

    invalid = client.post("/api/raw/routes/validate", json={"content": "{"})
    assert invalid.status_code == 400

    invalid_shape = client.post("/api/raw/routes/validate", json={"content": json.dumps({"foo": "bar"})})
    assert invalid_shape.status_code == 400

    class DummyProc:
        def __init__(self, stdout=b"ok", stderr=b""):
            self.stdout = stdout
            self.stderr = stderr

    def fake_run_ok(*args, **kwargs):
        return DummyProc(stdout=b"ok")

    def fake_run_fail(*args, **kwargs):
        raise __import__("subprocess").CalledProcessError(1, "caddy", stderr=b"bad config")

    monkeypatch.setattr("subprocess.run", fake_run_ok)
    ok = client.post("/api/raw/routes/validate", json={"content": json.dumps({"routes": []})})
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"

    def unlink_boom(_path):
        raise OSError("fail")

    monkeypatch.setattr("os.unlink", unlink_boom)
    ok2 = client.post("/api/raw/routes/validate", json={"content": json.dumps({"routes": []})})
    assert ok2.status_code == 200

    monkeypatch.setattr("subprocess.run", fake_run_fail)
    bad = client.post("/api/raw/routes/validate", json={"content": json.dumps({"routes": []})})
    assert bad.status_code == 400

    def fake_run_missing(*args, **kwargs):
        raise FileNotFoundError("no caddy")

    monkeypatch.setattr("subprocess.run", fake_run_missing)
    missing = client.post("/api/raw/routes/validate", json={"content": json.dumps({"routes": []})})
    assert missing.status_code == 503
