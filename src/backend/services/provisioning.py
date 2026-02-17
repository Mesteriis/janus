from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .. import settings
from ..caddy import write_caddy_config
from ..cloudflare.flow import sync_cloudflare_from_routes
from ..cloudflare.hostnames import cf_configured
from .errors import ServiceError
from ..core.context import correlation_context, ensure_correlation_id
from . import tunnel as tunnel_service

TRIGGER_CREATE = "create"
TRIGGER_REPLACE = "replace"
TRIGGER_RAW = "raw"
TRIGGER_PATCH = "patch"
TRIGGER_DELETE = "delete"
TRIGGER_L4 = "l4"
TRIGGER_PLUGINS = "plugins"

PROVISION_TRIGGERS: set[str] = {TRIGGER_CREATE, TRIGGER_REPLACE, TRIGGER_RAW}

logger = logging.getLogger(__name__)


def _run_caddy_validate() -> str | None:
    if not settings.CADDY_VALIDATE:
        return None
    try:
        completed = subprocess.run(
            [settings.CADDY_BIN, "validate", "--config", settings.CADDY_CONFIG, "--adapter", "json5"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        _ = completed.stdout
        return None
    except FileNotFoundError as exc:
        raise ServiceError(500, f"caddy executable not found: {exc}")
    except subprocess.CalledProcessError as exc:
        return (exc.stderr or b"").decode("utf-8").strip() or "caddy validate error"


def _restore_config(path: Path, content: str | None) -> None:
    if content is None:
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass
        return
    path.write_text(content, encoding="utf-8")


def _write_and_validate_config(data: dict) -> None:
    correlation_id = ensure_correlation_id()
    config_path = Path(settings.CADDY_CONFIG)
    old_content = None
    if config_path.exists():
        old_content = config_path.read_text(encoding="utf-8")

    write_caddy_config(data)
    error_text = _run_caddy_validate()
    if error_text:
        _restore_config(config_path, old_content)
        logger.error(
            "provisioning.rollback",
            extra={"event": "provisioning.rollback", "correlation_id": correlation_id, "error": error_text},
        )
        raise ServiceError(400, error_text)


def write_and_validate_config(data: dict, correlation_id: str | None = None) -> None:
    if correlation_id:
        with correlation_context(correlation_id):
            _write_and_validate_config(data)
        return
    _write_and_validate_config(data)


def ensure_tunnel_running() -> dict:
    return tunnel_service.ensure_running()


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
        logger.info(
            "provisioning.skip",
            extra={"event": "provisioning.skip", "correlation_id": correlation_id, "reason": "trigger"},
        )
        return _provision_result("skipped", reason="trigger")

    if not cf_configured():
        logger.info(
            "provisioning.skip",
            extra={"event": "provisioning.skip", "correlation_id": correlation_id, "reason": "cf_not_configured"},
        )
        return _cf_disabled_result()

    ensure_tunnel_running()
    try:
        result = await sync_cloudflare_from_routes(data)
        logger.info(
            "provisioning.success",
            extra={"event": "provisioning.success", "correlation_id": correlation_id},
        )
        return result
    except ServiceError as exc:
        logger.error(
            "provisioning.error",
            extra={"event": "provisioning.error", "correlation_id": correlation_id, "error": exc.detail},
        )
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "provisioning.error",
            extra={"event": "provisioning.error", "correlation_id": correlation_id, "error": str(exc)},
        )
        raise ServiceError(502, str(exc))


async def provision_after_routes_change(
    data: dict, trigger: str, correlation_id: str | None = None
) -> dict:
    if correlation_id:
        with correlation_context(correlation_id):
            return await _provision_after_routes_change(data, trigger)
    return await _provision_after_routes_change(data, trigger)
