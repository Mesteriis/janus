from __future__ import annotations

from .. import settings
from ..cloudflare.exception import CloudflareError
from ..cloudflare.flow import sync_cloudflare_from_routes as sync_cloudflare_flow
from ..cloudflare.hostnames import (
    apply_cloudflare_config,
    cf_configured,
    load_cf_hostnames,
    save_cf_hostnames,
    sync_cf_hostnames_from_routes,
)
from ..storage import load_routes
from .errors import ServiceError


def list_hostnames() -> dict:
    data = load_cf_hostnames()
    return {
        "configured": cf_configured(),
        "default_service": settings.CLOUDFLARE_DEFAULT_SERVICE,
        "hostnames": data.get("hostnames", []),
        "fallback": data.get("fallback", "http_status:404"),
    }


async def create_or_update_hostname(hostname: str, service: str, enabled: bool) -> dict:
    data = load_cf_hostnames()
    existing = next((entry for entry in data.get("hostnames", []) if entry["hostname"] == hostname), None)
    created = existing is None
    if existing:
        existing["service"] = service
        existing["enabled"] = enabled
    else:
        data.setdefault("hostnames", []).append({"hostname": hostname, "service": service, "enabled": enabled})

    save_cf_hostnames(data)
    return {"hostname": hostname, "service": service, "enabled": enabled, "created": created}


async def update_hostname(hostname: str, payload: dict) -> dict:
    data = load_cf_hostnames()
    for entry in data.get("hostnames", []):
        if entry["hostname"] != hostname:
            continue
        if "service" in payload:
            entry["service"] = payload["service"]
        if "enabled" in payload:
            entry["enabled"] = bool(payload["enabled"])
        save_cf_hostnames(data)
        return entry

    raise ServiceError(404, "Hostname not found")


async def delete_hostname(hostname: str) -> dict:
    data = load_cf_hostnames()
    hostnames = data.get("hostnames", [])
    updated = [entry for entry in hostnames if entry.get("hostname") != hostname]
    if len(updated) == len(hostnames):
        raise ServiceError(404, "Hostname not found")
    data["hostnames"] = updated
    save_cf_hostnames(data)
    return {"status": "deleted"}


async def apply() -> dict:
    hostnames_data = load_cf_hostnames()
    try:
        return await apply_cloudflare_config(hostnames_data)
    except CloudflareError as exc:
        raise ServiceError(502, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(502, str(exc))


async def sync_from_routes(data: dict | None = None) -> dict:
    routes_data = data or load_routes()
    try:
        hostnames_sync = sync_cf_hostnames_from_routes(routes_data)
        cloudflare_sync = await sync_cloudflare_flow(routes_data)
        payload = dict(cloudflare_sync)
        payload["hostnames_sync"] = hostnames_sync
        return payload
    except CloudflareError as exc:
        raise ServiceError(502, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(502, str(exc))
