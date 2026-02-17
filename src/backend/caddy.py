import json
from typing import Dict, List

from . import settings
from .plugins import default_plugins
from .utils import ensure_parent


def _path_matchers(path: str) -> List[str]:
    base = path.rstrip("/") or "/"
    if base == "/":
        return ["/"]
    return [base, f"{base}/*"]


def _bytes_from_mb(mb):
    try:
        return int(mb) * 1_000_000
    except (TypeError, ValueError):
        return None


def _headers_set(headers: dict) -> dict:
    return {name: [value] for name, value in headers.items()}


def _match_obj(domains, paths=None, methods=None, headers=None):
    obj = {"host": domains}
    if paths:
        obj["path"] = paths
    if methods:
        obj["method"] = methods
    if headers:
        obj["header"] = headers
    return obj


def _reverse_proxy_handler(route: dict) -> dict:
    upstreams = []
    for up in route.get("upstreams", []):
        target = f"{up['host']}:{up['port']}"
        if up.get("scheme") and up["scheme"] != "http":
            target = f"{up['scheme']}://{target}"
        upstreams.append(
            {
                "dial": target,
                **({"weight": up["weight"]} if up.get("weight") and up.get("weight") != 1 else {}),
            }
        )

    headers_up = route.get("headers_up") or {}
    headers_down = route.get("headers_down") or {}

    proxy = {
        "handler": "reverse_proxy",
        "upstreams": upstreams,
    }

    if route.get("lb_policy"):
        proxy["lb_policy"] = route["lb_policy"]

    if headers_up or headers_down:
        hdr = {}
        if headers_up:
            hdr["request"] = {"set": _headers_set(headers_up)}
        if headers_down:
            hdr["response"] = {"set": _headers_set(headers_down)}
        proxy["headers"] = hdr

    transport = route.get("transport") or {}
    timeouts = route.get("timeouts") or {}
    transport_cfg = {"protocol": "http"}
    if timeouts.get("connect"):
        transport_cfg["dial_timeout"] = f"{timeouts['connect']}s"
    if timeouts.get("read"):
        transport_cfg["read_timeout"] = f"{timeouts['read']}s"
    if timeouts.get("write"):
        transport_cfg["write_timeout"] = f"{timeouts['write']}s"
    if transport.get("dial_timeout"):
        transport_cfg["dial_timeout"] = transport["dial_timeout"]
    if transport.get("read_buffer"):
        transport_cfg["read_buffer_size"] = transport["read_buffer"]
    if transport.get("write_buffer"):
        transport_cfg["write_buffer_size"] = transport["write_buffer"]
    if transport.get("keepalive"):
        transport_cfg.setdefault("keep_alive", {})["idle_timeout"] = transport["keepalive"]
    if transport.get("tls_insecure"):
        transport_cfg.setdefault("tls", {})["insecure_skip_verify"] = True
    if len(transport_cfg.keys()) > 1:
        proxy["transport"] = transport_cfg

    health_active = route.get("health_active") or {}
    health_passive = route.get("health_passive") or {}
    if health_active or health_passive:
        health_cfg = {}
        if health_active:
            active = {
                "uri": health_active.get("path"),
            }
            if health_active.get("interval"):
                active["interval"] = health_active["interval"]
            if health_active.get("timeout"):
                active["timeout"] = health_active["timeout"]
            if health_active.get("headers"):
                active["headers"] = health_active["headers"]
            health_cfg["active"] = active
        if health_passive:
            passive = {}
            if health_passive.get("unhealthy_statuses"):
                passive["unhealthy_status"] = health_passive["unhealthy_statuses"]
            if health_passive.get("max_fails"):
                passive["max_fails"] = health_passive["max_fails"]
            if health_passive.get("fail_duration"):
                passive["fail_duration"] = health_passive["fail_duration"]
            health_cfg["passive"] = passive
        proxy["health_checks"] = health_cfg

    proxy_opts = route.get("proxy_opts") or {}
    if proxy_opts.get("flush_interval"):
        proxy["flush_interval"] = proxy_opts["flush_interval"]

    return proxy


def _build_handlers(route: dict, response_headers: dict, request_body_max_mb):
    handlers = []
    if request_body_max_mb is not None:
        handlers.append({"handler": "request_body", "max_size": _bytes_from_mb(request_body_max_mb)})
    if response_headers:
        handlers.append({"handler": "headers", "response": {"set": _headers_set(response_headers)}})

    rate_limit = route.get("rate_limit") or {}
    if rate_limit:
        rl = {
            "handler": "rate_limit",
            "rate_limits": {
                "default": {
                    "key": rate_limit.get("key", "remote_ip"),
                    "window": rate_limit.get("window", "10s"),
                    "max": rate_limit.get("max", 10),
                }
            },
        }
        if rate_limit.get("burst"):
            rl["rate_limits"]["default"]["burst"] = rate_limit["burst"]
        handlers.append(rl)

    if route.get("redirect"):
        redirect = route["redirect"]
        handlers.append(
            {
                "handler": "static_response",
                "status_code": redirect.get("code", 302),
                "headers": {"Location": [redirect.get("location") or ""]},
            }
        )
    elif route.get("respond"):
        resp = route["respond"]
        body = resp.get("body") if resp.get("body") is not None else ""
        handler = {"handler": "static_response", "status_code": resp.get("status", 200)}
        if body != "":
            handler["body"] = body
        if resp.get("content_type"):
            handler.setdefault("headers", {})["Content-Type"] = [resp["content_type"]]
        handlers.append(handler)
    else:
        wd = route.get("webdav") or {}
        if wd.get("enabled"):
            handler = {"handler": "webdav", "root": wd.get("root", "/")}
            if wd.get("username"):
                handler["username"] = wd["username"]
            if wd.get("password"):
                handler["password"] = wd["password"]
            if wd.get("methods"):
                handler["methods"] = wd["methods"]
            handlers.append(handler)
        else:
            handlers.append(_reverse_proxy_handler(route))
            wd = None

    if route.get("replace_response"):
        rep = route["replace_response"]
        rep_handler = {"handler": "replace_response", "replacements": [{"search": rep["find"], "replace": rep["replace"]}]}
        if rep.get("status"):
            rep_handler["status_code"] = rep["status"]
        handlers.append(rep_handler)

    return handlers


def _route_block(domains, route: dict) -> dict:
    response_headers = route.get("response_headers") or {}
    request_body_max_mb = route.get("request_body_max_mb")

    match = _match_obj(domains, None, route.get("methods") or [], route.get("match_headers") or {})
    handlers = _build_handlers(route, response_headers, request_body_max_mb)

    return {"match": [match], "handle": handlers}


def _path_route_block(domains, base_route: dict, path_route: dict) -> dict:
    response_headers = base_route.get("response_headers") or {}
    request_body_max_mb = base_route.get("request_body_max_mb")
    paths = _path_matchers(path_route["path"])
    match = _match_obj(domains, paths, path_route.get("methods") or [], path_route.get("match_headers") or {})

    handlers = []
    if request_body_max_mb is not None:
        handlers.append({"handler": "request_body", "max_size": _bytes_from_mb(request_body_max_mb)})
    if response_headers:
        handlers.append({"handler": "headers", "response": {"set": _headers_set(response_headers)}})
    if path_route.get("strip_prefix"):
        handlers.append({"handler": "rewrite", "strip_path_prefix": path_route["path"]})

    if path_route.get("redirect"):
        redirect = path_route["redirect"]
        handlers.append(
            {
                "handler": "static_response",
                "status_code": redirect.get("code", 302),
                "headers": {"Location": [redirect.get("location") or ""]},
            }
        )
    elif path_route.get("respond"):
        resp = path_route["respond"]
        body = resp.get("body") if resp.get("body") is not None else ""
        handler = {"handler": "static_response", "status_code": resp.get("status", 200)}
        if body != "":
            handler["body"] = body
        if resp.get("content_type"):
            handler.setdefault("headers", {})["Content-Type"] = [resp["content_type"]]
        handlers.append(handler)
    else:
        handlers.append(_reverse_proxy_handler(path_route))

    return {"match": [match], "handle": handlers}


def _options_route(domains, response_headers: dict, status: int, request_body_max_mb):
    match = _match_obj(domains, None, ["OPTIONS"], None)
    handlers = []
    if request_body_max_mb is not None:
        handlers.append({"handler": "request_body", "max_size": _bytes_from_mb(request_body_max_mb)})
    if response_headers:
        handlers.append({"handler": "headers", "response": {"set": _headers_set(response_headers)}})
    handlers.append({"handler": "static_response", "status_code": status, "body": ""})
    return {"match": [match], "handle": handlers}


def render_caddy_config(data: Dict) -> Dict:
    http_routes = []
    routes = data.get("routes", [])
    plugins = data.get("plugins") or default_plugins()

    for route in routes:
        if not route.get("enabled", True):
            continue
        domains = route.get("domains", [])
        if not domains:
            continue

        route.setdefault("upstreams", [])
        if not route["upstreams"] and route.get("upstream"):
            route["upstreams"] = [route["upstream"]]
        if not route["upstreams"]:
            continue
        route.setdefault("lb_policy", "round_robin")
        route.setdefault("proxy_opts", {})
        route.setdefault("transport", {})

        response_headers = route.get("response_headers") or {}
        options_response = route.get("options_response") or {}

        path_routes = sorted(
            [pr for pr in route.get("path_routes") or [] if pr.get("enabled", True)],
            key=lambda item: len(item.get("path", "")),
            reverse=True,
        )
        for pr in path_routes:
            if not pr.get("upstreams") and pr.get("upstream"):
                pr["upstreams"] = [pr["upstream"]]
            if not pr.get("upstreams"):
                continue
            http_routes.append(_path_route_block(domains, route, pr))

        if options_response.get("enabled"):
            http_routes.append(
                _options_route(domains, response_headers, options_response.get("status", 204), route.get("request_body_max_mb"))
            )

        http_routes.append(_route_block(domains, route))

    http_server = {
        "listen": [":80", ":443"],
        "routes": http_routes,
        "automatic_https": {},
    }

    errors_root = str(settings.CADDY_ERRORS_DIR) if getattr(settings, "CADDY_ERRORS_DIR", None) else ""
    if errors_root:
        http_server["errors"] = {
            "routes": [
                {
                    "handle": [
                        {"handler": "rewrite", "uri": "/{http.error.status_code}.html"},
                        {"handler": "file_server", "root": errors_root},
                    ]
                }
            ]
        }

    extra_http_routes = []
    if plugins.get("prometheus", {}).get("enabled"):
        path = plugins["prometheus"].get("path") or "/metrics"
        extra_http_routes.append({"match": [{"path": [path]}], "handle": [{"handler": "prometheus"}]})
    if plugins.get("trace", {}).get("enabled"):
        exporter = plugins["trace"].get("exporter") or {}
        trace_handler = {"handler": "trace"}
        if exporter.get("otlp_endpoint"):
            trace_handler["exporter"] = {"otlp_endpoint": exporter["otlp_endpoint"]}
            if exporter.get("headers"):
                trace_handler["exporter"]["headers"] = exporter["headers"]
        extra_http_routes.append({"handle": [trace_handler]})
    http_server["routes"] = extra_http_routes + http_routes

    config = {"apps": {"http": {"servers": {"srv0": http_server}}}}

    if settings.CADDY_EMAIL:
        config.setdefault("apps", {}).setdefault("tls", {}).setdefault("automation", {}).setdefault("policies", []).append(
            {"issuers": [{"module": "acme", "email": settings.CADDY_EMAIL}]}
        )

    tls_redis_addr = plugins.get("tlsredis", {}).get("address") or settings.TLS_REDIS_ADDRESS
    if tls_redis_addr:
        storage = {"module": "redis", "address": tls_redis_addr}
        tlsredis = plugins.get("tlsredis", {})
        if tlsredis.get("db") is not None:
            storage["db"] = tlsredis.get("db")
        if tlsredis.get("username"):
            storage["username"] = tlsredis["username"]
        if tlsredis.get("password"):
            storage["password"] = tlsredis["password"]
        if tlsredis.get("key_prefix"):
            storage["key_prefix"] = tlsredis["key_prefix"]
        config["storage"] = storage

    l4_routes = data.get("l4_routes") or []
    if l4_routes:
        l4_server = {"listen": [], "routes": []}
        for lr in l4_routes:
            listen = lr.get("listen") or ""
            if listen and listen not in l4_server["listen"]:
                l4_server["listen"].append(listen)
            match = {}
            if lr.get("match", {}).get("sni"):
                match["sni"] = lr["match"]["sni"]
            if lr.get("match", {}).get("alpn"):
                match["alpn"] = lr["match"]["alpn"]
            handles = []
            proxy = lr.get("proxy") or {}
            ups_list = []
            for up in proxy.get("upstreams", []):
                dial = up.get("dial") or up.get("address") or ""
                if dial:
                    ups_list.append({"dial": dial})
            if ups_list:
                p = {"handler": "proxy", "upstreams": ups_list}
                if proxy.get("idle_timeout"):
                    p["idle_timeout"] = proxy["idle_timeout"]
                if proxy.get("max_connections"):
                    p["max_connections"] = proxy["max_connections"]
                handles.append(p)
            l4_server["routes"].append({"match": [match] if match else [], "handle": handles})
        config.setdefault("apps", {}).setdefault("layer4", {}).setdefault("servers", {})["l4srv"] = l4_server

    return config


def write_caddy_config(data: Dict) -> None:
    ensure_parent(settings.CADDY_CONFIG)
    config = render_caddy_config(data)
    with open(settings.CADDY_CONFIG, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
