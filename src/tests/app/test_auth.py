from pathlib import Path


def test_auth_status_disabled(client_factory):
    client, _ = client_factory()
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["authorized"] is True


def test_auth_enabled_requires_cookie(client_factory, tmp_path):
    password_file = tmp_path / "auth.txt"
    password_file.write_text("secret", encoding="utf-8")
    client, _ = client_factory(AUTH_PASSWORD_FILE=str(password_file))

    resp = client.get("/api/routes")
    assert resp.status_code == 401

    client.cookies.set("janus_auth", "secret")
    resp2 = client.get("/api/routes")
    assert resp2.status_code == 200


def test_auth_login_and_logout(client_factory, tmp_path):
    password_file = tmp_path / "auth.txt"
    password_file.write_text("secret", encoding="utf-8")
    client, _ = client_factory(AUTH_PASSWORD_FILE=str(password_file))

    bad = client.post("/api/auth/login", json={"password": "nope"})
    assert bad.status_code == 401

    ok = client.post("/api/auth/login", json={"password": "secret"})
    assert ok.status_code == 200

    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.json()["enabled"] is True
    assert status.json()["authorized"] is True

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    status2 = client.get("/api/auth/status")
    assert status2.status_code == 200
    assert status2.json()["authorized"] is False


def test_auth_login_payload_validation(client_factory, tmp_path):
    password_file = tmp_path / "auth.txt"
    password_file.write_text("secret", encoding="utf-8")
    client, _ = client_factory(AUTH_PASSWORD_FILE=str(password_file))

    empty = client.post("/api/auth/login", json={})
    assert empty.status_code == 400

    empty2 = client.post("/api/auth/login", json={"password": ""})
    assert empty2.status_code == 400


def test_auth_disabled_login_returns_ok(client_factory):
    client, _ = client_factory()
    resp = client.post("/api/auth/login", json={"password": "whatever"})
    assert resp.status_code == 200
    assert resp.json()["authorized"] is True


def test_auth_password_read_error(monkeypatch, tmp_path):
    from app import auth, settings

    password_file = tmp_path / "auth.txt"
    password_file.write_text("secret", encoding="utf-8")

    monkeypatch.setattr(settings, "AUTH_PASSWORD_FILE", password_file)
    auth._cache["mtime"] = None

    def _broken_read(_self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", _broken_read)
    assert auth.get_password() == ""


def test_auth_options_passes_through(client_factory, tmp_path):
    password_file = tmp_path / "auth.txt"
    password_file.write_text("secret", encoding="utf-8")
    client, _ = client_factory(AUTH_PASSWORD_FILE=str(password_file))

    resp = client.options("/api/routes")
    assert resp.status_code == 405


def test_auth_config_enable_disable(client_factory, tmp_path):
    password_file = tmp_path / "auth.txt"
    client, _ = client_factory(AUTH_PASSWORD_FILE=str(password_file))

    enable = client.put("/api/auth/config", json={"enabled": True, "password": "secret"})
    assert enable.status_code == 200
    assert enable.json()["enabled"] is True
    assert password_file.read_text(encoding="utf-8").strip() == "secret"

    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.json()["authorized"] is True

    disable = client.put("/api/auth/config", json={"enabled": False})
    assert disable.status_code == 200
    assert disable.json()["enabled"] is False
    assert not password_file.exists() or password_file.read_text(encoding="utf-8").strip() == ""


def test_auth_config_disable_requires_password(client_factory, tmp_path):
    password_file = tmp_path / "auth.txt"
    password_file.write_text("secret", encoding="utf-8")
    client, _ = client_factory(AUTH_PASSWORD_FILE=str(password_file))

    resp = client.put("/api/auth/config", json={"enabled": False})
    assert resp.status_code == 401


def test_auth_config_validation_errors(client_factory):
    client, _ = client_factory()

    missing = client.put("/api/auth/config", json={})
    assert missing.status_code == 400

    missing_password = client.put("/api/auth/config", json={"enabled": True})
    assert missing_password.status_code == 400

    bad_enabled = client.put("/api/auth/config", json={"enabled": "yes"})
    assert bad_enabled.status_code == 400


def test_set_password_stat_error(monkeypatch, tmp_path):
    from app import auth, settings

    password_file = tmp_path / "auth.txt"
    monkeypatch.setattr(settings, "AUTH_PASSWORD_FILE", password_file)

    def _stat(_self):
        raise OSError("boom")

    monkeypatch.setattr(Path, "stat", _stat)
    auth.set_password("secret")
    assert auth._cache["value"] == "secret"


def test_set_password_unlink_error(monkeypatch, tmp_path):
    from app import auth, settings

    password_file = tmp_path / "auth.txt"
    password_file.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(settings, "AUTH_PASSWORD_FILE", password_file)

    def _unlink(_self):
        raise OSError("boom")

    def _write_text(_self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "unlink", _unlink)
    monkeypatch.setattr(Path, "write_text", _write_text)
    auth.set_password("")
    assert auth._cache["value"] == ""
