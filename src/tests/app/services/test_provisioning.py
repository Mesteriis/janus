import asyncio

import pytest


def test_run_caddy_validate_file_not_found(monkeypatch, reload_settings):
    from app.services import provisioning

    monkeypatch.setenv("CADDY_VALIDATE", "1")
    reload_settings()

    def boom(*args, **kwargs):
        raise FileNotFoundError("nope")

    monkeypatch.setattr("backend.services.provisioning.subprocess.run", boom)
    with pytest.raises(provisioning.ServiceError):
        provisioning._run_caddy_validate()


def test_run_caddy_validate_success(monkeypatch, reload_settings):
    from app.services import provisioning

    monkeypatch.setenv("CADDY_VALIDATE", "1")
    reload_settings()

    class DummyProc:
        stdout = b"ok"
        stderr = b""

    monkeypatch.setattr("backend.services.provisioning.subprocess.run", lambda *a, **k: DummyProc())
    assert provisioning._run_caddy_validate() is None


def test_run_caddy_validate_calledprocess(monkeypatch, reload_settings):
    from app.services import provisioning
    import subprocess

    monkeypatch.setenv("CADDY_VALIDATE", "1")
    reload_settings()

    def boom(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "caddy", stderr=b"bad")

    monkeypatch.setattr("backend.services.provisioning.subprocess.run", boom)
    assert provisioning._run_caddy_validate() == "bad"


def test_run_caddy_validate_skipped(monkeypatch, reload_settings):
    from app.services import provisioning

    monkeypatch.setenv("CADDY_VALIDATE", "0")
    reload_settings()

    def boom(*args, **kwargs):
        raise AssertionError("should not run caddy validate")

    monkeypatch.setattr("backend.services.provisioning.subprocess.run", boom)
    assert provisioning._run_caddy_validate() is None


def test_write_and_validate_config_success(monkeypatch, tmp_path, reload_settings):
    from app.services import provisioning
    from app.plugins import default_plugins

    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    reload_settings()

    monkeypatch.setattr(provisioning, "_run_caddy_validate", lambda: None)
    data = {"routes": [], "plugins": default_plugins(), "l4_routes": []}
    provisioning.write_and_validate_config(data)
    assert (tmp_path / "config.json5").exists()


def test_write_and_validate_config_with_correlation_id(monkeypatch, tmp_path, reload_settings):
    from app.services import provisioning
    from app.plugins import default_plugins
    from app.core.context import get_correlation_id, reset_correlation_id, set_correlation_id

    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    reload_settings()

    monkeypatch.setattr(provisioning, "_run_caddy_validate", lambda: None)
    data = {"routes": [], "plugins": default_plugins(), "l4_routes": []}
    token = set_correlation_id("base")
    try:
        provisioning.write_and_validate_config(data, correlation_id="cid-cli")
        assert (tmp_path / "config.json5").exists()
        assert get_correlation_id() == "base"
    finally:
        reset_correlation_id(token)


def test_write_and_validate_config_rollback(monkeypatch, tmp_path, reload_settings):
    from app.services import provisioning
    from app.plugins import default_plugins

    config_path = tmp_path / "config.json5"
    config_path.write_text("old")

    monkeypatch.setenv("CADDY_CONFIG", str(config_path))
    reload_settings()

    monkeypatch.setattr(provisioning, "_run_caddy_validate", lambda: "bad config")
    data = {"routes": [], "plugins": default_plugins(), "l4_routes": []}
    with pytest.raises(provisioning.ServiceError):
        provisioning.write_and_validate_config(data)
    assert config_path.read_text() == "old"


def test_write_and_validate_config_no_old(monkeypatch, tmp_path, reload_settings):
    from app.services import provisioning
    from app.plugins import default_plugins

    config_path = tmp_path / "config.json5"
    monkeypatch.setenv("CADDY_CONFIG", str(config_path))
    reload_settings()

    monkeypatch.setattr(provisioning, "_run_caddy_validate", lambda: "bad config")
    data = {"routes": [], "plugins": default_plugins(), "l4_routes": []}
    with pytest.raises(provisioning.ServiceError):
        provisioning.write_and_validate_config(data)
    assert not config_path.exists()


def test_restore_config_unlink_error():
    from app.services import provisioning

    class DummyPath:
        def exists(self):
            return True

        def unlink(self):
            raise RuntimeError("fail")

    provisioning._restore_config(DummyPath(), None)


@pytest.mark.asyncio
async def test_provision_after_routes_change_skip_trigger(monkeypatch):
    from app.services import provisioning

    called = {"write": 0}

    def _write(_data, **_kw):
        called["write"] += 1

    monkeypatch.setattr(provisioning, "write_and_validate_config", _write)
    res = await provisioning.provision_after_routes_change({"routes": []}, provisioning.TRIGGER_PATCH)
    assert res["status"] == "skipped"
    assert called["write"] == 1


@pytest.mark.asyncio
async def test_provision_after_routes_change_cf_disabled(monkeypatch):
    from app.services import provisioning

    monkeypatch.setattr(provisioning, "write_and_validate_config", lambda _d, **_kw: None)
    monkeypatch.setattr(provisioning, "cf_configured", lambda: False)

    res = await provisioning.provision_after_routes_change({"routes": []}, provisioning.TRIGGER_CREATE)
    assert res["status"] == "skipped"


@pytest.mark.asyncio
async def test_provision_after_routes_change_success(monkeypatch):
    from app.services import provisioning

    monkeypatch.setattr(provisioning, "write_and_validate_config", lambda _d, **_kw: None)
    monkeypatch.setattr(provisioning, "cf_configured", lambda: True)
    monkeypatch.setattr(provisioning, "ensure_tunnel_running", lambda: {"status": "running"})

    async def _sync(data):
        return {"status": "ok", "domains": 0}

    monkeypatch.setattr(provisioning, "sync_cloudflare_from_routes", _sync)
    res = await provisioning.provision_after_routes_change({"routes": []}, provisioning.TRIGGER_CREATE)
    assert res["status"] == "ok"


@pytest.mark.asyncio
async def test_provision_after_routes_change_cli_correlation(monkeypatch):
    from app.services import provisioning
    from app.core.context import get_correlation_id, reset_correlation_id, set_correlation_id

    seen = {}

    def _write(_data, **_kw):
        seen["cid"] = get_correlation_id()

    monkeypatch.setattr(provisioning, "write_and_validate_config", _write)
    monkeypatch.setattr(provisioning, "cf_configured", lambda: False)

    token = set_correlation_id("base")
    try:
        res = await provisioning.provision_after_routes_change(
            {"routes": []}, provisioning.TRIGGER_CREATE, correlation_id="cli-1"
        )
        assert res["status"] == "skipped"
        assert seen["cid"] == "cli-1"
        assert get_correlation_id() == "base"
    finally:
        reset_correlation_id(token)


@pytest.mark.asyncio
async def test_provision_after_routes_change_cf_error(monkeypatch):
    from app.services import provisioning

    monkeypatch.setattr(provisioning, "write_and_validate_config", lambda _d, **_kw: None)
    monkeypatch.setattr(provisioning, "cf_configured", lambda: True)
    monkeypatch.setattr(provisioning, "ensure_tunnel_running", lambda: {"status": "running"})

    async def _sync(_data):
        raise RuntimeError("boom")

    monkeypatch.setattr(provisioning, "sync_cloudflare_from_routes", _sync)
    with pytest.raises(provisioning.ServiceError):
        await provisioning.provision_after_routes_change({"routes": []}, provisioning.TRIGGER_CREATE)


@pytest.mark.asyncio
async def test_provision_after_routes_change_service_error(monkeypatch):
    from app.services import provisioning
    from app.services.errors import ServiceError

    monkeypatch.setattr(provisioning, "write_and_validate_config", lambda _d, **_kw: None)
    monkeypatch.setattr(provisioning, "cf_configured", lambda: True)
    monkeypatch.setattr(provisioning, "ensure_tunnel_running", lambda: {"status": "running"})

    async def _sync(_data):
        raise ServiceError(502, "boom")

    monkeypatch.setattr(provisioning, "sync_cloudflare_from_routes", _sync)
    with pytest.raises(ServiceError):
        await provisioning.provision_after_routes_change({"routes": []}, provisioning.TRIGGER_CREATE)


def test_ensure_tunnel_running_proxy(monkeypatch):
    from app.services import provisioning

    class Dummy:
        @staticmethod
        def ensure_running():
            return {"status": "running"}

    monkeypatch.setattr(provisioning, "tunnel_service", Dummy)
    assert provisioning.ensure_tunnel_running()["status"] == "running"


@pytest.mark.asyncio
async def test_provisioning_logs_start_skip(caplog, monkeypatch):
    from app.services import provisioning

    monkeypatch.setattr(provisioning, "write_and_validate_config", lambda _d, **_kw: None)
    monkeypatch.setattr(provisioning, "cf_configured", lambda: False)

    with caplog.at_level("INFO"):
        res = await provisioning.provision_after_routes_change({"routes": []}, provisioning.TRIGGER_CREATE)
        assert res["status"] == "skipped"
        assert any("provisioning.start" in rec.message for rec in caplog.records)
        assert any("provisioning.skip" in rec.message for rec in caplog.records)


def test_provisioning_logs_rollback(caplog, monkeypatch, tmp_path, reload_settings):
    from app.services import provisioning
    from app.plugins import default_plugins
    from app.core.context import set_correlation_id, reset_correlation_id

    config_path = tmp_path / "config.json5"
    monkeypatch.setenv("CADDY_CONFIG", str(config_path))
    reload_settings()

    monkeypatch.setattr(provisioning, "_run_caddy_validate", lambda: "bad config")
    data = {"routes": [], "plugins": default_plugins(), "l4_routes": []}

    with caplog.at_level("ERROR"):
        token = set_correlation_id("cid-1")
        try:
            with pytest.raises(provisioning.ServiceError):
                provisioning.write_and_validate_config(data)
        finally:
            reset_correlation_id(token)
        assert any("provisioning.rollback" in rec.message for rec in caplog.records)


def test_provisioning_helpers():
    from app.services import provisioning

    res = provisioning._provision_result("ok", reason="x")
    assert res["status"] == "ok"
    assert res["reason"] == "x"

    res2 = provisioning._cf_disabled_result()
    assert res2["reason"] == "cf_not_configured"
