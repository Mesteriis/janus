import re
import uuid
from typing import Dict, List

from . import settings


def normalize_domains(domains: List[str]) -> List[str]:
    cleaned = []
    for raw in domains or []:
        value = raw.strip().lower()
        if value:
            cleaned.append(value)
    return cleaned


def parse_headers(header_lines):
    headers = {}
    for line in header_lines or []:
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid header line: {line}")
        name, value = line.split(":", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            raise ValueError(f"Invalid header name in line: {line}")
        headers[name] = value
    return headers


def parse_header_values(header_lines):
    if isinstance(header_lines, dict):
        cleaned = {}
        for name, values in header_lines.items():
            if isinstance(values, list):
                cleaned[name] = [str(v).strip() for v in values if str(v).strip()]
            else:
                cleaned[name] = [str(values).strip()] if str(values).strip() else []
        return cleaned
    headers = {}
    for line in header_lines or []:
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid header line: {line}")
        name, value = line.split(":", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            raise ValueError(f"Invalid header name in line: {line}")
        parts = [v for v in re.split(r"[\s,]+", value) if v]
        if not parts:
            raise ValueError(f"Invalid header value in line: {line}")
        headers[name] = parts
    return headers


def validate_domain(domain: str) -> bool:
    return bool(settings.DOMAIN_RE.match(domain))


def validate_port(port) -> bool:
    try:
        port_int = int(port)
    except (TypeError, ValueError):
        return False
    return 1 <= port_int <= 65535


def validate_scheme(scheme: str) -> bool:
    return scheme in {"http", "https"}


def validate_path(path: str) -> bool:
    return path.startswith("/") and " " not in path


def duration(value, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return f"{int(value)}s"
    value = str(value).strip()
    if not value:
        return default
    if value[-1].isdigit():
        return f"{value}s"
    return value


def collect_timeouts(payload):
    timeouts = payload.get("timeouts") or {}
    cleaned = {}
    for key in ("connect", "read", "write"):
        value = timeouts.get(key)
        if value is None or value == "":
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Timeout {key} must be a number")
        if number < 0:
            raise ValueError(f"Timeout {key} must be >= 0")
        cleaned[key] = number
    return cleaned


def validate_upstream(upstream: Dict) -> Dict:
    scheme = (upstream.get("scheme") or "http").lower()
    if not validate_scheme(scheme):
        raise ValueError("Invalid upstream scheme")
    host = (upstream.get("host") or "").strip()
    if not host or " " in host:
        raise ValueError("Invalid upstream host")
    port = upstream.get("port")
    if not validate_port(port):
        raise ValueError("Invalid upstream port")
    weight = upstream.get("weight", 1)
    try:
        weight = int(weight)
    except (TypeError, ValueError):
        raise ValueError("Invalid upstream weight")
    if weight < 1:
        raise ValueError("Upstream weight must be >= 1")
    return {"scheme": scheme, "host": host, "port": int(port), "weight": weight}


def validate_rate_limit(value: Dict) -> Dict | None:
    if not value:
        return None
    key = (value.get("key") or "remote_ip").strip()
    window = value.get("window") or "10s"
    max_events = value.get("max") or value.get("events") or value.get("limit")
    burst = value.get("burst")
    try:
        max_events = int(max_events)
    except (TypeError, ValueError):
        raise ValueError("rate_limit.max must be number")
    if max_events < 1:
        raise ValueError("rate_limit.max must be >=1")
    if burst:
        try:
            burst = int(burst)
        except (TypeError, ValueError):
            raise ValueError("rate_limit.burst must be number")
    return {"key": key, "window": window, "max": max_events, "burst": burst}


def validate_replace_response(value: Dict) -> Dict | None:
    if not value:
        return None
    find = value.get("find")
    replace = value.get("replace")
    if not find:
        return None
    status = value.get("status")
    if status:
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = None
    return {"find": str(find), "replace": str(replace or ""), "status": status}


def validate_webdav(value: Dict) -> Dict | None:
    if not value:
        return None
    if not value.get("enabled"):
        return None
    root = (value.get("root") or "/").strip() or "/"
    username = value.get("username") or ""
    password = value.get("password") or ""
    methods = value.get("methods") or []
    return {"enabled": True, "root": root, "username": username, "password": password, "methods": methods}


def validate_route_payload(payload: Dict) -> Dict:
    domains = normalize_domains(payload.get("domains") or [])
    if not domains:
        raise ValueError("At least one domain is required")
    for domain in domains:
        if not validate_domain(domain):
            raise ValueError(f"Invalid domain: {domain}")

    methods = []
    for m in payload.get("methods") or []:
        val = m.strip().upper()
        if not val:
            continue
        if not settings.METHOD_RE.match(val):
            raise ValueError(f"Invalid method: {val}")
        methods.append(val)
    match_headers = parse_header_values(payload.get("match_headers", []))

    upstreams = payload.get("upstreams") or []
    validated_upstreams = [validate_upstream(u) for u in upstreams]
    if not validated_upstreams:
        validated_upstreams.append(validate_upstream(payload.get("upstream") or {}))

    lb_policy = (payload.get("lb_policy") or "").strip() or "round_robin"

    request_body_max_mb = payload.get("request_body_max_mb")
    if request_body_max_mb is not None and request_body_max_mb != "":
        try:
            request_body_max_mb = int(request_body_max_mb)
        except (TypeError, ValueError):
            raise ValueError("Max body size must be a number")
        if request_body_max_mb < 0:
            raise ValueError("Max body size must be >= 0")
    else:
        request_body_max_mb = None

    headers_up = parse_headers(payload.get("headers_up", []))
    headers_down = parse_headers(payload.get("headers_down", []))
    response_headers = parse_headers(payload.get("response_headers", []))

    timeouts = collect_timeouts(payload)

    health_active = payload.get("health_active") or {}
    if health_active:
        path = (health_active.get("path") or "").strip()
        if not path:
            raise ValueError("Active health check requires path")
        interval = duration(health_active.get("interval"))
        timeout = duration(health_active.get("timeout"))
        headers_health = parse_header_values(health_active.get("headers", []))
        health_active = {
            "path": path,
            "interval": interval,
            "timeout": timeout,
            "headers": headers_health,
        }
    else:
        health_active = None

    health_passive = payload.get("health_passive") or {}
    if health_passive:
        statuses = health_passive.get("unhealthy_statuses") or []
        cleaned_statuses = []
        for status in statuses:
            try:
                status_int = int(status)
            except (TypeError, ValueError):
                raise ValueError("Invalid unhealthy status code")
            if status_int < 100 or status_int > 599:
                raise ValueError("Invalid unhealthy status code")
            cleaned_statuses.append(status_int)
        max_fails = health_passive.get("max_fails")
        if max_fails is not None and max_fails != "":
            try:
                max_fails = int(max_fails)
            except (TypeError, ValueError):
                raise ValueError("max_fails must be a number")
            if max_fails < 1:
                raise ValueError("max_fails must be >= 1")
        else:
            max_fails = None
        fail_duration = duration(health_passive.get("fail_duration"))
        health_passive = {
            "unhealthy_statuses": cleaned_statuses,
            "max_fails": max_fails,
            "fail_duration": fail_duration,
        }
    else:
        health_passive = None

    transport = payload.get("transport") or {}
    if transport:
        transport = {
            "dial_timeout": duration(transport.get("dial_timeout")),
            "read_buffer": transport.get("read_buffer"),
            "write_buffer": transport.get("write_buffer"),
            "keepalive": duration(transport.get("keepalive")),
            "tls_insecure": bool(transport.get("tls_insecure", False)),
        }
    else:
        transport = {}

    proxy_opts = payload.get("proxy_opts") or {}
    proxy_opts = {
        "flush_interval": duration(proxy_opts.get("flush_interval")),
        "buffer_requests": bool(proxy_opts.get("buffer_requests", False)),
        "buffer_responses": bool(proxy_opts.get("buffer_responses", False)),
    }

    redirect = payload.get("redirect") or {}
    if redirect and redirect.get("location"):
        try:
            code = int(redirect.get("code", 302))
        except (TypeError, ValueError):
            raise ValueError("Redirect code must be number")
        if code < 100 or code > 599:
            raise ValueError("Redirect code must be valid HTTP status")
        redirect = {"location": redirect.get("location"), "code": code}
    else:
        redirect = None

    respond = payload.get("respond") or {}
    if respond and respond.get("status"):
        try:
            status = int(respond.get("status"))
        except (TypeError, ValueError):
            raise ValueError("Respond status must be number")
        if status < 100 or status > 599:
            raise ValueError("Respond status must be valid HTTP status")
        respond = {
            "status": status,
            "body": respond.get("body") or "",
            "content_type": respond.get("content_type") or "",
        }
    else:
        respond = None

    path_routes = []
    for route in payload.get("path_routes") or []:
        path = (route.get("path") or "").strip()
        if not path:
            continue
        if not validate_path(path):
            raise ValueError(f"Invalid path: {path}")
        overrides_upstreams = route.get("upstreams") or []
        validated_overrides = [validate_upstream(up) for up in overrides_upstreams] or [validate_upstream(route.get("upstream") or {})]

        route_methods = []
        for m in route.get("methods") or []:
            val = m.strip().upper()
            if val:
                if not settings.METHOD_RE.match(val):
                    raise ValueError(f"Invalid method: {val}")
                route_methods.append(val)
        route_headers = parse_header_values(route.get("match_headers", []))

        route_redirect = route.get("redirect") or {}
        if route_redirect and route_redirect.get("location"):
            code = int(route_redirect.get("code", 302))
            route_redirect = {"location": route_redirect.get("location"), "code": code}
        else:
            route_redirect = None
        route_respond = route.get("respond") or {}
        if route_respond and route_respond.get("status"):
            status = int(route_respond.get("status"))
            route_respond = {
                "status": status,
                "body": route_respond.get("body") or "",
                "content_type": route_respond.get("content_type") or "",
            }
        else:
            route_respond = None

        path_routes.append(
            {
                "id": route.get("id") or str(uuid.uuid4()),
                "path": path,
                "strip_prefix": bool(route.get("strip_prefix", False)),
                "enabled": bool(route.get("enabled", True)),
                "upstreams": validated_overrides,
                "timeouts": collect_timeouts(route),
                "methods": route_methods,
                "match_headers": route_headers,
                "redirect": route_redirect,
                "respond": route_respond,
            }
        )

    options_response = payload.get("options_response") or {}
    if options_response:
        enabled = bool(options_response.get("enabled", False))
        status = int(options_response.get("status", 204))
        if status < 100 or status > 599:
            raise ValueError("Invalid OPTIONS response status")
        options_response = {"enabled": enabled, "status": status}
    else:
        options_response = None

    return {
        "domains": domains,
        "enabled": bool(payload.get("enabled", True)),
        "tls_enabled": bool(payload.get("tls_enabled", True)),
        "methods": methods,
        "match_headers": match_headers,
        "upstreams": validated_upstreams,
        "lb_policy": lb_policy,
        "request_body_max_mb": request_body_max_mb,
        "headers_up": headers_up,
        "headers_down": headers_down,
        "response_headers": response_headers,
        "timeouts": timeouts,
        "health_active": health_active,
        "health_passive": health_passive,
        "transport": transport,
        "proxy_opts": proxy_opts,
        "redirect": redirect,
        "respond": respond,
        "path_routes": path_routes,
        "options_response": options_response,
        "rate_limit": validate_rate_limit(payload.get("rate_limit") or {}),
        "cache_override": payload.get("cache_override") or None,
        "replace_response": validate_replace_response(payload.get("replace_response") or {}),
        "webdav": validate_webdav(payload.get("webdav") or {}),
        "realip_override": payload.get("realip_override") or None,
        "geoip_override": payload.get("geoip_override") or None,
    }
