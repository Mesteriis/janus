import ipaddress
from pathlib import Path

from .. import settings
from ..storage import load_routes
from .client import CloudFlare
from .constants import DnsException
from .exception import CloudflareError
from .hostnames import resolve_cf_token


def _iter_upstreams(route: dict):
    if isinstance(route.get("upstreams"), list) and route["upstreams"]:
        for up in route["upstreams"]:
            if isinstance(up, dict):
                yield up
    elif isinstance(route.get("upstream"), dict):
        yield route["upstream"]


def _extract_ssh_exceptions(routes_data: dict) -> dict[str, list[DnsException]]:
    exceptions: dict[str, list[DnsException]] = {}

    def add_exception(domain: str, host: str):
        record_type = "CNAME"
        try:
            ip = ipaddress.ip_address(host)
            record_type = "AAAA" if ip.version == 6 else "A"
        except ValueError:
            pass
        entry = DnsException(fqdn=domain, record_type=record_type, content=host)
        exceptions.setdefault(domain, []).append(entry)

    for route in routes_data.get("routes", []):
        domains = route.get("domains") or []
        # main upstreams
        for up in _iter_upstreams(route):
            if str(up.get("port")) == "22" and up.get("host"):
                for d in domains:
                    add_exception(d, str(up["host"]))
        # path routes
        for pr in route.get("path_routes") or []:
            for up in _iter_upstreams(pr):
                if str(up.get("port")) == "22" and up.get("host"):
                    for d in domains:
                        add_exception(d, str(up["host"]))

    # L4 routes (optional)
    for l4 in routes_data.get("l4_routes") or []:
        listen = str(l4.get("listen") or "")
        port = listen.split(":")[-1] if ":" in listen else listen
        if port != "22":
            continue
        sni_list = (l4.get("match") or {}).get("sni") or []
        proxy = l4.get("proxy") or {}
        for up in proxy.get("upstreams") or []:
            host = up.get("host")
            if not host and up.get("dial"):
                dial = str(up.get("dial"))
                if "://" in dial:
                    dial = dial.split("://", 1)[1]
                host = dial.rsplit(":", 1)[0] if ":" in dial else dial
            if not host:
                continue
            for d in sni_list:
                add_exception(d, str(host))

    return exceptions


async def sync_cloudflare_from_routes(data: dict | None = None) -> dict:
    if data is None:
        data = load_routes()
    domains: set[str] = set()

    for route in data.get("routes", []):
        for d in route.get("domains") or []:
            if d:
                domains.add(d.strip().lower())

    state_file = Path(settings.CF_STATE_FILE)
    cf = CloudFlare(state_file=state_file)

    token = resolve_cf_token() or None
    if await cf.bootstrap():
        token = None

    if token:
        await cf.set_token(token, persist=True)

    if not cf.ready:
        return {"status": "skipped", "reason": "token_missing_or_invalid", "domains": len(domains)}

    # If no domains, only token verification is needed.
    if not domains:
        return {"status": "ok", "domains": 0}

    exceptions_by_domain = _extract_ssh_exceptions(data)
    zones: dict[str, dict] = {}

    for domain in sorted(domains):
        try:
            zone_info = await cf.resolve_zone_for_hostname(domain)
        except CloudflareError:
            continue
        zone = zone_info["zone"]
        zones.setdefault(zone, {"domains": set(), "exceptions": []})
        zones[zone]["domains"].add(domain)
        if domain in exceptions_by_domain:
            zones[zone]["exceptions"].extend(exceptions_by_domain[domain])

    results = []
    for zone, info in zones.items():
        res = await cf.provision_all_to_caddy(
            zone=zone,
            caddy_url=settings.CLOUDFLARE_DEFAULT_SERVICE or "http://127.0.0.1:80",
            dns_exceptions=info["exceptions"],
        )
        results.append(res)

    return {"status": "ok", "zones": results, "domains": len(domains)}
