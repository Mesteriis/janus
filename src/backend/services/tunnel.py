from __future__ import annotations

from .. import settings
from ..docker_ctl import start_tunnel, stop_tunnel, tunnel_status
from .errors import ServiceError


def start(token: str | None = None) -> dict:
    token = token or settings.CLOUDFLARE_TUNNEL_TOKEN
    if not token:
        raise ServiceError(400, "CLOUDFLARE_TUNNEL_TOKEN is empty")
    try:
        return start_tunnel(token)
    except ValueError as exc:
        raise ServiceError(400, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(500, str(exc))


def stop() -> dict:
    try:
        return stop_tunnel()
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(500, str(exc))


def status() -> dict:
    try:
        return tunnel_status()
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(500, str(exc))


def ensure_running() -> dict:
    token = settings.CLOUDFLARE_TUNNEL_TOKEN
    if not token:
        raise ServiceError(400, "CLOUDFLARE_TUNNEL_TOKEN is empty")
    state = status()
    if state.get("status") == "running":
        return state
    return start(token)
