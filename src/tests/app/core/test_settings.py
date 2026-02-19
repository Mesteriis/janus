import importlib
import json


def test_settings_path_normalization(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_ROOT", "relroot")
    monkeypatch.setenv("ROUTES_FILE", "rel/routes.json")
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "abs.json5"))
    monkeypatch.setenv("CADDY_ERRORS_DIR", "rel/errors")
    monkeypatch.setenv("SETTINGS_JSON_FILE", "rel/app_settings.json")
    monkeypatch.setenv("AUTH_PASSWORD_FILE", "rel/auth.txt")
    monkeypatch.setenv("CLOUDFLARE_HOSTNAMES_FILE", "rel/hosts.json")
    monkeypatch.setenv("CLOUDFLARE_STATE_FILE", "rel/state.json")
    monkeypatch.setenv("CF_TUNNEL_DIR", "rel/cloudflared")

    from app.core.config import Settings

    settings = Settings()
    root = settings.project_root
    assert settings.routes_file == root / "rel/routes.json"
    assert settings.caddy_config == tmp_path / "abs.json5"
    assert settings.caddy_errors_dir == root / "rel/errors"
    assert settings.settings_json_file == root / "rel/app_settings.json"
    assert settings.auth_password_file == root / "rel/auth.txt"
    assert settings.cloudflare_hostnames_file == root / "rel/hosts.json"
    assert settings.cloudflare_state_file == root / "rel/state.json"
    assert settings.cf_tunnel_dir.endswith("rel/cloudflared")


def test_settings_feature_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("FEATURE_TUNNEL_ENABLED", "false")
    monkeypatch.setenv("FEATURE_VPN_ENABLED", "0")
    monkeypatch.setenv("SETTINGS_JSON_FILE", str(tmp_path / "app_settings.json"))

    from app.core.config import Settings

    settings = Settings()
    assert settings.feature_tunnel_enabled is False
    assert settings.feature_vpn_enabled is False


def test_settings_loaded_from_json_file(monkeypatch, tmp_path):
    json_path = tmp_path / "app_settings.json"
    json_path.write_text(
        json.dumps(
            {
                "dashboard_port": 9099,
                "feature_tunnel_enabled": False,
                "feature_vpn_enabled": False,
                "cloudflare_default_service": "http://example.internal:18080",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SETTINGS_JSON_FILE", str(json_path))
    monkeypatch.setenv("DASHBOARD_PORT", "8090")

    from app.core.config import Settings

    settings = Settings()
    assert settings.dashboard_port == 9099
    assert settings.feature_tunnel_enabled is False
    assert settings.feature_vpn_enabled is False
    assert settings.cloudflare_default_service == "http://example.internal:18080"


def test_configure_logging(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    from app.core.logging import configure_logging

    configure_logging()


def test_correlation_id_filter():
    import logging
    from app.core.context import set_correlation_id, reset_correlation_id
    from app.core.logging import CorrelationIdFilter

    token = set_correlation_id("cid-123")
    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        filt = CorrelationIdFilter()
        assert filt.filter(record) is True
        assert record.correlation_id == "cid-123"
    finally:
        reset_correlation_id(token)


def test_correlation_context_sets_and_resets():
    from app.core.context import correlation_context, get_correlation_id, reset_correlation_id, set_correlation_id

    token = set_correlation_id("base")
    try:
        with correlation_context("cid-cli") as cid:
            assert cid == "cid-cli"
            assert get_correlation_id() == "cid-cli"
        assert get_correlation_id() == "base"
    finally:
        reset_correlation_id(token)


def test_lifespan_handles_exception(monkeypatch, tmp_path):
    import importlib

    monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    import app.settings as settings
    import app.storage as storage
    import app.caddy as caddy

    importlib.reload(settings)
    importlib.reload(storage)
    importlib.reload(caddy)

    lifespan = importlib.import_module("backend.core.lifespan")
    service = importlib.import_module("backend.services.lifespan")

    async def boom():
        raise RuntimeError("fail")

    monkeypatch.setattr(service, "sync_cloudflare_from_routes", boom)
    # avoid caddy validate in this test
    monkeypatch.setattr(service, "write_and_validate_config", lambda _d: None)

    # run startup
    async def _run():
        await service.sync_cloudflare_on_startup()
        async with lifespan.lifespan(None):
            return True

    import asyncio

    asyncio.run(_run())
