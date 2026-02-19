from __future__ import annotations

import json
import inspect
import logging
import os
import subprocess
from pathlib import Path

from .. import settings
from ..caddy import render_caddy_config
from ..caddyfile import write_caddyfile
from ..cloudflare.hostnames import cf_configured
from ..core.context import correlation_context, ensure_correlation_id
from . import caddy_runtime as caddy_runtime_service
from . import cloudflare as cloudflare_service
from . import tunnel as tunnel_service
from .errors import ServiceError

TRIGGER_CREATE = "create"
TRIGGER_REPLACE = "replace"
TRIGGER_RAW = "raw"
TRIGGER_PATCH = "patch"
TRIGGER_DELETE = "delete"
TRIGGER_L4 = "l4"
TRIGGER_PLUGINS = "plugins"

PROVISION_TRIGGERS: set[str] = {
    TRIGGER_CREATE,
    TRIGGER_REPLACE,
    TRIGGER_RAW,
    TRIGGER_PATCH,
    TRIGGER_DELETE,
    TRIGGER_L4,
    TRIGGER_PLUGINS,
}

logger = logging.getLogger(__name__)


def _run_caddy_validate() -> str | None:
    if not settings.CADDY_VALIDATE:
        return None
    try:
        subprocess.run(
            [settings.CADDY_BIN, "validate", "--config", str(settings.CADDY_CONFIG)],
            capture_output=True,
            check=True,
        )
        return None
    except FileNotFoundError as exc:
        raise ServiceError(500, f"Caddy binary not found: {settings.CADDY_BIN}") from exc
    except subprocess.CalledProcessError as exc:
        return (exc.stderr or b"").decode("utf-8", errors="ignore").strip() or "Caddy validate failed"


def _restore_config(config_path: Path, old_content: str | None) -> None:
    try:
        if old_content is None:
            if config_path.exists():
                config_path.unlink()
            return
        config_path.write_text(old_content, encoding="utf-8")
    except Exception:  # noqa: BLE001
        logger.exception("provisioning.rollback")


def write_and_validate_config(data: dict, correlation_id: str | None = None) -> None:
    def _write() -> None:
        config_path = settings.CADDY_CONFIG
        config_path.parent.mkdir(parents=True, exist_ok=True)
        old_content = config_path.read_text(encoding="utf-8") if config_path.exists() else None
        try:
            # Runtime is Caddyfile-based; keep JSON config artifact valid for diagnostics and optional validation.
            write_caddyfile(data)
            caddy_json_config = render_caddy_config(data)
            config_path.write_text(json.dumps(caddy_json_config, ensure_ascii=False, indent=2), encoding="utf-8")
            error = _run_caddy_validate()
            if error:
                logger.error("provisioning.rollback")
                _restore_config(config_path, old_content)
                raise ServiceError(400, error)
            # Keep running Caddy runtime in sync with freshly rendered Caddyfile.
            if not os.getenv("PYTEST_CURRENT_TEST"):
                caddy_runtime_service.apply_caddyfile()
        except ServiceError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("provisioning.rollback")
            _restore_config(config_path, old_content)
            raise ServiceError(500, str(exc)) from exc

    if correlation_id:
        with correlation_context(correlation_id):
            _write()
        return
    _write()


def ensure_tunnel_running() -> dict:
    ensure = getattr(tunnel_service, "ensure_running", None)
    if callable(ensure):
        try:
            return ensure()
        except ServiceError as exc:
            # In managed Cloudflare flow we use API token + per-tunnel token and
            # may not have legacy CLOUDFLARE_TUNNEL_TOKEN env configured.
            if exc.status_code == 400 and "CLOUDFLARE_TUNNEL_TOKEN is empty" in str(exc.detail or ""):
                logger.info("provisioning.skip")
                return {"status": "skipped", "reason": "legacy_tunnel_token_not_configured"}
            raise
    return {"status": "skipped", "reason": "tunnel_disabled"}


def sync_cloudflare_from_routes(data: dict) -> dict:
    return cloudflare_service.sync_from_routes(data)


def should_provision(trigger: str) -> bool:
    return trigger in PROVISION_TRIGGERS


def _provision_result(status: str, **extra) -> dict:
    payload = {"status": status}
    payload.update(extra)
    return payload


def _cf_disabled_result() -> dict:
    return _provision_result("skipped", reason="cf_not_configured")


async def _provision_after_routes_change(data: dict, trigger: str) -> dict:
    correlation_id = ensure_correlation_id()
    logger.info(
        "provisioning.start",
        extra={"event": "provisioning.start", "correlation_id": correlation_id, "trigger": trigger},
    )
    write_and_validate_config(data)

    if not should_provision(trigger):
        logger.info("provisioning.skip")
        return _provision_result("skipped", reason="trigger_not_supported")

    if not cf_configured():
        logger.info("provisioning.skip")
        return _cf_disabled_result()

    ensure_tunnel_running()
    try:
        result = sync_cloudflare_from_routes(data)
        if inspect.isawaitable(result):
            return await result
        return result
    except ServiceError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(502, str(exc)) from exc


async def provision_after_routes_change(
    data: dict, trigger: str, correlation_id: str | None = None
) -> dict:
    if correlation_id:
        with correlation_context(correlation_id):
            return await _provision_after_routes_change(data, trigger)
    return await _provision_after_routes_change(data, trigger)
