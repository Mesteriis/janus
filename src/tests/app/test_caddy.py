import importlib


def test_render_caddy_config_full(tmp_path, monkeypatch, reload_settings):
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    monkeypatch.setenv("CADDY_EMAIL", "test@example.com")
    monkeypatch.setenv("TLS_REDIS_ADDRESS", "redis:6379")
    monkeypatch.setenv("CADDY_ERRORS_DIR", "/config/errors")

    from app import caddy

    reload_settings()
    importlib.reload(caddy)

    assert caddy._path_matchers("/") == ["/"]
    assert caddy._bytes_from_mb("bad") is None

    data = {
        "plugins": {
            "tlsredis": {"address": "redis:6379", "db": 1, "username": "u", "password": "p", "key_prefix": "k"},
            "prometheus": {"enabled": True, "path": "/metrics"},
            "trace": {"enabled": True, "exporter": {"otlp_endpoint": "http://otel:4318", "headers": {"X": "1"}}},
        },
        "routes": [
            {
                "domains": ["example.com"],
                "enabled": True,
                "methods": ["GET"],
                "match_headers": {"X-Test": ["1"]},
                "upstreams": [{"scheme": "https", "host": "up", "port": 80, "weight": 2}],
                "lb_policy": "round_robin",
                "request_body_max_mb": 1,
                "headers_up": {"X-Up": "yes"},
                "headers_down": {"X-Down": "yes"},
                "response_headers": {"X-Resp": "yes"},
                "timeouts": {"connect": 1, "read": 2, "write": 3},
                "health_active": {"path": "/health", "interval": "5s", "timeout": "2s", "headers": {"X": ["1"]}},
                "health_passive": {"unhealthy_statuses": [500], "max_fails": 2, "fail_duration": "10s"},
                "transport": {"dial_timeout": "1s", "read_buffer": 1024, "write_buffer": 2048, "keepalive": "5s", "tls_insecure": True},
                "proxy_opts": {"flush_interval": "1s"},
                "rate_limit": {"key": "remote_ip", "window": "10s", "max": 5, "burst": 2},
                "replace_response": {"find": "a", "replace": "b", "status": 200},
                "path_routes": [
                    {
                        "path": "/api",
                        "strip_prefix": True,
                        "enabled": True,
                        "upstreams": [{"scheme": "http", "host": "api", "port": 8080, "weight": 1}],
                        "methods": ["GET"],
                        "match_headers": {"X-P": ["1"]},
                        "redirect": {"location": "https://example.com/api", "code": 302},
                    },
                    {
                        "path": "/resp",
                        "enabled": True,
                        "upstreams": [{"scheme": "http", "host": "api", "port": 8081, "weight": 1}],
                        "respond": {"status": 418, "body": "hi", "content_type": "text/plain"},
                    },
                    {
                        "path": "/proxy",
                        "enabled": True,
                        "upstream": {"scheme": "http", "host": "api", "port": 8082, "weight": 1},
                    },
                    {
                        "path": "/skip",
                        "enabled": True,
                    },
                ],
                "options_response": {"enabled": True, "status": 204},
            },
            {
                "domains": ["redirect.example.com"],
                "enabled": True,
                "upstreams": [{"scheme": "http", "host": "up", "port": 80, "weight": 1}],
                "redirect": {"location": "https://example.com", "code": 301},
            },
            {
                "domains": ["respond.example.com"],
                "enabled": True,
                "upstreams": [{"scheme": "http", "host": "up", "port": 80, "weight": 1}],
                "respond": {"status": 200, "body": "ok", "content_type": "text/plain"},
            },
            {
                "domains": ["dav.example.com"],
                "enabled": True,
                "upstreams": [{"scheme": "http", "host": "up", "port": 80, "weight": 1}],
                "webdav": {"enabled": True, "root": "/data", "username": "u", "password": "p", "methods": ["GET"]},
            },
            {
                "domains": ["disabled.example.com"],
                "enabled": False,
                "upstreams": [{"scheme": "http", "host": "up", "port": 80, "weight": 1}],
            },
            {
                "domains": [],
                "enabled": True,
                "upstreams": [{"scheme": "http", "host": "up", "port": 80, "weight": 1}],
            },
            {
                "domains": ["noup.example.com"],
                "enabled": True,
                "upstreams": [],
            },
            {
                "domains": ["singleup.example.com"],
                "enabled": True,
                "upstream": {"scheme": "http", "host": "up", "port": 8080, "weight": 1},
            },
        ],
        "l4_routes": [
            {
                "listen": ":22",
                "match": {"sni": ["ssh.example.com"], "alpn": ["ssh"]},
                "proxy": {
                    "upstreams": [{"dial": "10.0.0.1:22"}, {"address": "10.0.0.2:22"}],
                    "idle_timeout": "10s",
                    "max_connections": 10,
                },
            },
            {"listen": ":1234", "proxy": {"upstreams": []}},
        ],
    }

    config = caddy.render_caddy_config(data)
    assert "apps" in config
    assert "http" in config["apps"]
    assert "layer4" in config["apps"]
    assert config["storage"]["module"] == "redis"
    assert config["apps"]["http"]["servers"]["srv0"]["errors"]["routes"][0]["handle"][1]["root"] == "/config/errors"

    # write config file
    caddy.write_caddy_config(data)
    assert (tmp_path / "config.json5").exists()
