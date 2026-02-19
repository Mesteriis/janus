from __future__ import annotations

from pathlib import Path
from typing import Any

from . import settings
from .utils import ensure_parent


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _as_duration(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text[-1].isdigit():
        return f"{text}s"
    return text


def _errors_root() -> str:
    configured = getattr(settings, "CADDY_ERRORS_DIR", None)
    static_dir = getattr(settings, "STATIC_DIR", None)
    if configured and Path(configured).exists():
        return str(Path(configured))
    if static_dir:
        return str(Path(static_dir))
    candidates: list[Path] = [
        settings.PROJECT_ROOT / "docker" / "caddy" / "errors",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def _target_from_upstream(upstream: dict[str, Any]) -> str:
    scheme = (upstream.get("scheme") or "http").strip()
    host = (upstream.get("host") or "127.0.0.1").strip()
    port = upstream.get("port")
    base = f"{host}:{port}" if port else host
    if scheme and scheme != "http":
        return f"{scheme}://{base}"
    return base


def _upstream_targets(route: dict[str, Any]) -> list[str]:
    upstreams = route.get("upstreams") or []
    if upstreams:
        return [_target_from_upstream(upstream) for upstream in upstreams if upstream]
    upstream = route.get("upstream") or {}
    if upstream:
        return [_target_from_upstream(upstream)]
    return []


def _header_lines(headers: dict[str, str] | None, indent: str = "    ") -> list[str]:
    values = headers or {}
    if not values:
        return []
    lines = [f"{indent}header {{"]
    for key, value in values.items():
        lines.append(f"{indent}    {key} {_escape(str(value))}")
    lines.append(f"{indent}}}")
    return lines


def _request_body_lines(route: dict[str, Any], indent: str = "    ") -> list[str]:
    mb = route.get("request_body_max_mb")
    if mb is None:
        return []
    return [
        f"{indent}request_body {{",
        f"{indent}    max_size {mb}MB",
        f"{indent}}}",
    ]


def _proxy_block_lines(
    route: dict[str, Any],
    indent: str = "    ",
    *,
    include_headers_import: bool = True,
) -> list[str]:
    targets = _upstream_targets(route)
    if not targets:
        return [f'{indent}respond "Route has no upstream" 502']

    headers_up = route.get("headers_up") or {}
    timeouts = route.get("timeouts") or {}
    transport = route.get("transport") or {}
    health_active = route.get("health_active") or {}
    health_passive = route.get("health_passive") or {}
    lb_policy = (route.get("lb_policy") or "").strip()

    lines = [f"{indent}reverse_proxy {' '.join(targets)} {{"]
    if include_headers_import:
        lines.append(f"{indent}    import janus_proxy_headers")
    if len(targets) > 1 and lb_policy:
        lines.append(f"{indent}    lb_policy {lb_policy}")
    for key, value in headers_up.items():
        lines.append(f"{indent}    header_up {key} {_escape(str(value))}")

    transport_lines: list[str] = []
    dial_timeout = _as_duration(transport.get("dial_timeout") or timeouts.get("connect"))
    read_timeout = _as_duration(timeouts.get("read"))
    write_timeout = _as_duration(timeouts.get("write"))
    if dial_timeout:
        transport_lines.append(f"{indent}        dial_timeout {dial_timeout}")
    if read_timeout:
        transport_lines.append(f"{indent}        read_timeout {read_timeout}")
    if write_timeout:
        transport_lines.append(f"{indent}        write_timeout {write_timeout}")
    if transport.get("read_buffer"):
        transport_lines.append(f"{indent}        read_buffer {int(transport['read_buffer'])}")
    if transport.get("write_buffer"):
        transport_lines.append(f"{indent}        write_buffer {int(transport['write_buffer'])}")
    if transport.get("keepalive"):
        transport_lines.append(f"{indent}        keepalive {_as_duration(transport['keepalive'])}")
    if transport.get("tls_insecure"):
        transport_lines.append(f"{indent}        tls_insecure_skip_verify")
    if transport_lines:
        lines.append(f"{indent}    transport http {{")
        lines.extend(transport_lines)
        lines.append(f"{indent}    }}")

    if health_active.get("path"):
        lines.append(f"{indent}    health_uri {health_active['path']}")
    if health_active.get("interval"):
        lines.append(f"{indent}    health_interval {health_active['interval']}")
    if health_active.get("timeout"):
        lines.append(f"{indent}    health_timeout {health_active['timeout']}")
    for key, value in (health_active.get("headers") or {}).items():
        lines.append(f"{indent}    health_header {key} {_escape(str(value))}")

    if health_passive.get("max_fails"):
        lines.append(f"{indent}    max_fails {int(health_passive['max_fails'])}")
    if health_passive.get("fail_duration"):
        lines.append(f"{indent}    fail_duration {health_passive['fail_duration']}")
    for status in health_passive.get("unhealthy_statuses") or []:
        lines.append(f"{indent}    unhealthy_status {int(status)}")

    lines.append(f"{indent}}}")
    return lines


def _respond_lines(route: dict[str, Any], indent: str = "    ") -> list[str]:
    respond = route.get("respond") or {}
    status = int(respond.get("status") or 200)
    body = _escape(str(respond.get("body") or ""))
    content_type = (respond.get("content_type") or "").strip()
    lines: list[str] = []
    if content_type:
        lines.extend(
            [
                f"{indent}header {{",
                f"{indent}    Content-Type {content_type}",
                f"{indent}}}",
            ]
        )
    lines.append(f'{indent}respond "{body}" {status}')
    return lines


def _redirect_lines(route: dict[str, Any], indent: str = "    ") -> list[str]:
    redirect = route.get("redirect") or {}
    location = (redirect.get("location") or "").strip()
    code = int(redirect.get("code") or 302)
    if not location:
        return [f'{indent}respond "Redirect location is empty" 500']
    return [f"{indent}redir {location} {code}"]


def _route_behavior_lines(route: dict[str, Any], indent: str = "    ") -> list[str]:
    if route.get("redirect"):
        return _redirect_lines(route, indent=indent)
    if route.get("respond"):
        return _respond_lines(route, indent=indent)
    return _proxy_block_lines(route, indent=indent)


def _path_route_lines(route: dict[str, Any], indent: str = "    ") -> list[str]:
    lines: list[str] = []
    for path_route in route.get("path_routes") or []:
        if not path_route.get("enabled", True):
            continue
        path = (path_route.get("path") or "").strip()
        if not path.startswith("/"):
            continue
        directive = "handle_path" if path_route.get("strip_prefix") else "handle"
        lines.append(f"{indent}{directive} {path}* {{")
        lines.extend(_route_behavior_lines(path_route, indent=f"{indent}    "))
        lines.append(f"{indent}}}")
    return lines


def _options_lines(route: dict[str, Any], indent: str = "    ") -> list[str]:
    options = route.get("options_response") or {}
    if not options.get("enabled"):
        return []
    status = int(options.get("status") or 204)
    return [
        f"{indent}@preflight method OPTIONS",
        f"{indent}respond @preflight \"\" {status}",
    ]


def _plugin_comment_lines(plugins: dict[str, Any], indent: str = "# ") -> list[str]:
    lines = [f"{indent}Plugins snapshot:"]
    for name, value in sorted((plugins or {}).items()):
        if isinstance(value, dict) and "enabled" in value:
            flag = "on" if value.get("enabled") else "off"
            lines.append(f"{indent}{name}: {flag}")
        elif isinstance(value, dict):
            compact = ", ".join(
                f"{k}={v}" for k, v in value.items() if v not in ("", None, [], {})
            )
            lines.append(f"{indent}{name}: {compact or 'configured'}")
        else:
            lines.append(f"{indent}{name}: {value}")
    return lines


def _global_block_lines(data: dict[str, Any]) -> list[str]:
    lines = ["{"]
    if settings.CADDY_EMAIL:
        lines.append(f"    email {settings.CADDY_EMAIL}")
    tlsredis = (data.get("plugins") or {}).get("tlsredis") or {}
    address = (tlsredis.get("address") or settings.TLS_REDIS_ADDRESS or "").strip()
    if address:
        lines.extend(
            [
                "    storage redis {",
                f"        address {address}",
            ]
        )
        if tlsredis.get("db") is not None:
            lines.append(f"        db {int(tlsredis['db'])}")
        if tlsredis.get("username"):
            lines.append(f"        username {tlsredis['username']}")
        if tlsredis.get("password"):
            lines.append(f"        password {tlsredis['password']}")
        if tlsredis.get("key_prefix"):
            lines.append(f"        key_prefix {tlsredis['key_prefix']}")
        lines.append("    }")
    lines.append("}")
    return lines


def _shared_snippets(errors_root: str) -> list[str]:
    lines = [
        "(janus_proxy_headers) {",
        "    header_up Host {host}",
        "    header_up X-Real-IP {remote_host}",
        "    header_up X-Forwarded-For {remote_host}",
        "    header_up X-Forwarded-Proto {scheme}",
        "    header_up X-Forwarded-Host {host}",
        "}",
    ]
    if errors_root:
        lines.extend(
            [
                "",
                "(janus_error_pages) {",
                "    handle_errors {",
                f"        root * {errors_root}",
                "        rewrite * /{err.status_code}.html",
                "        file_server",
                "    }",
                "}",
            ]
        )
    return lines


def _site_lines(route: dict[str, Any], errors_root: str) -> list[str]:
    tls_enabled = bool(route.get("tls_enabled", True))
    addresses: list[str] = []
    for domain in route.get("domains") or []:
        value = str(domain or "").strip()
        if not value:
            continue
        if not tls_enabled and "://" not in value and not value.startswith(":"):
            value = f"http://{value}"
        addresses.append(value)
    lines = [f"{', '.join(addresses)} {{"]
    if errors_root:
        lines.append("    import janus_error_pages")
    lines.extend(_request_body_lines(route))
    lines.extend(_header_lines(route.get("response_headers")))
    lines.extend(_options_lines(route))
    lines.extend(_path_route_lines(route))
    lines.extend(_route_behavior_lines(route))
    lines.append("}")
    return lines


def render_caddyfile(data: dict[str, Any]) -> str:
    plugins = data.get("plugins") or {}
    errors_root = _errors_root()
    lines: list[str] = ["# Managed by Janus", ""]
    lines.extend(_global_block_lines(data))
    lines.append("")
    lines.extend(_plugin_comment_lines(plugins))
    lines.append("")
    lines.extend(_shared_snippets(errors_root))
    lines.append("")

    routes = data.get("routes") or []
    enabled_routes = [r for r in routes if r.get("enabled", True) and r.get("domains")]

    if not enabled_routes:
        lines.extend(
            [
                ":80 {",
                "    import janus_error_pages" if errors_root else "",
                "    respond \"No routes configured\" 200",
                "}",
            ]
        )
        return "\n".join([line for line in lines if line != ""]) + "\n"

    for route in enabled_routes:
        lines.extend(_site_lines(route, errors_root))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_caddyfile(data: dict[str, Any]) -> None:
    content = render_caddyfile(data)
    ensure_parent(settings.CADDYFILE_PATH)
    settings.CADDYFILE_PATH.write_text(content, encoding="utf-8")


def write_default_caddyfile(data: dict[str, Any] | None = None) -> str:
    payload = data or {"routes": []}
    write_caddyfile(payload)
    return str(settings.CADDYFILE_PATH)
