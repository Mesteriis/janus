from __future__ import annotations

import json
from pathlib import Path

from .. import settings
from ..storage import load_routes
from ..utils import ensure_parent
from ..validation import validate_domain
from .client import CloudFlare
from .exception import CloudflareError


def cf_configured() -> bool:
    if settings.CLOUDFLARE_API_TOKEN:
        return True
    try:
        state = Path(settings.CF_STATE_FILE)
        if state.exists():
            data = json.loads(state.read_text() or "{}")
            return bool(data.get("api_token"))
    except Exception:
        return False
    return False


def validate_cf_service(service: str) -> bool:
    if service.startswith("http_status:"):
        code = service.split(":", 1)[1]
        return code.isdigit()
    if service == "hello_world":
        return True
    if service.startswith(("http://", "https://", "tcp://", "ssh://", "rdp://", "unix:")):
        return True
    return False


def cf_default_fallback() -> str:
    fallback = settings.CLOUDFLARE_DEFAULT_SERVICE or "http_status:404"
    if validate_cf_service(fallback):
        return fallback
    return "http_status:404"


def _normalize_hostnames(data: dict) -> dict:
    fallback = data.get("fallback") or cf_default_fallback()
    hostnames = []
    for entry in data.get("hostnames", []):
        if not isinstance(entry, dict):
            continue
        hostname = (entry.get("hostname") or "").strip().lower()
        if not hostname:
            continue
        service = (entry.get("service") or "").strip() or settings.CLOUDFLARE_DEFAULT_SERVICE
        enabled = bool(entry.get("enabled", True))
        hostnames.append({"hostname": hostname, "service": service, "enabled": enabled})
    return {"hostnames": hostnames, "fallback": fallback}


def load_cf_hostnames() -> dict:
    default_fallback = cf_default_fallback()
    if not settings.CLOUDFLARE_HOSTNAMES_FILE:
        return {"hostnames": [], "fallback": default_fallback}
    try:
        with open(settings.CLOUDFLARE_HOSTNAMES_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        ensure_parent(settings.CLOUDFLARE_HOSTNAMES_FILE)
        data = {"hostnames": [], "fallback": default_fallback}
    if "hostnames" not in data:
        data["hostnames"] = []
    if not data.get("fallback"):
        data["fallback"] = default_fallback
    return _normalize_hostnames(data)


def save_cf_hostnames(data: dict) -> None:
    ensure_parent(settings.CLOUDFLARE_HOSTNAMES_FILE)
    payload = _normalize_hostnames(data)
    with open(settings.CLOUDFLARE_HOSTNAMES_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def sync_cf_hostnames_from_routes(routes_data: dict) -> dict:
    data = load_cf_hostnames()

    hostnames_map = {entry["hostname"]: entry for entry in data.get("hostnames", [])}
    added = 0
    updated = 0
    skipped = 0

    for route in routes_data.get("routes", []):
        for domain in route.get("domains", []):
            hostname = domain.strip().lower()
            if not hostname or not validate_domain(hostname):
                skipped += 1
                continue
            existing = hostnames_map.get(hostname)
            if existing:
                if existing.get("enabled") != route.get("enabled", True):
                    existing["enabled"] = bool(route.get("enabled", True))
                    updated += 1
                continue
            hostnames_map[hostname] = {
                "hostname": hostname,
                "service": settings.CLOUDFLARE_DEFAULT_SERVICE,
                "enabled": bool(route.get("enabled", True)),
            }
            added += 1

    data["hostnames"] = list(hostnames_map.values())
    save_cf_hostnames(data)
    return {"added": added, "updated": updated, "skipped": skipped}


async def apply_cloudflare_config(data: dict) -> dict:
    data = _normalize_hostnames(data)
    hostnames = [h for h in data.get("hostnames", []) if h.get("enabled", True)]
    fallback = data.get("fallback") or cf_default_fallback()
    if not validate_cf_service(fallback):
        fallback = cf_default_fallback()

    state_file = Path(settings.CF_STATE_FILE)
    cf = CloudFlare(state_file=state_file)

    token = settings.CLOUDFLARE_API_TOKEN or None
    if await cf.bootstrap():
        token = None
    if token:
        await cf.set_token(token, persist=True)

    if not cf.ready:
        raise CloudflareError("Cloudflare API not configured")

    # If no hostnames, only token verification is needed.
    if not hostnames:
        return {"status": "ok", "domains": 0}

    # optional exceptions for port 22 from routes
    from .flow import _extract_ssh_exceptions

    exceptions_by_domain = _extract_ssh_exceptions(load_routes())

    zones: dict[str, dict] = {}
    for entry in hostnames:
        hostname = entry["hostname"]
        try:
            zone_info = await cf.resolve_zone_for_hostname(hostname)
        except CloudflareError:
            continue
        zone = zone_info["zone"]
        zones.setdefault(zone, {"entries": [], "exceptions": []})
        zones[zone]["entries"].append(
            {
                "hostname": hostname,
                "service": entry.get("service") or settings.CLOUDFLARE_DEFAULT_SERVICE,
            }
        )
        if hostname in exceptions_by_domain:
            zones[zone]["exceptions"].extend(exceptions_by_domain[hostname])

    results = []
    for zone, info in zones.items():
        res = await cf.provision_all_to_caddy(
            zone=zone,
            caddy_url=settings.CLOUDFLARE_DEFAULT_SERVICE or "http://127.0.0.1:80",
            dns_exceptions=info["exceptions"],
            extra_ingress=info["entries"],
            fallback_service=fallback,
        )
        results.append(res)

    return {"status": "ok", "zones": results, "domains": len(hostnames)}
