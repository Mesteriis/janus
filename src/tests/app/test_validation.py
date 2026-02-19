import importlib
import json

import pytest


def test_utils_read_write_json(tmp_path):
    from backend import utils

    path = tmp_path / "a" / "data.json"
    utils.write_json(str(path), {"ok": True})
    loaded = utils.read_json(str(path), {})
    assert loaded["ok"] is True

    missing = utils.read_json(str(tmp_path / "missing" / "x.json"), {"fallback": 1})
    assert missing["fallback"] == 1


def test_storage_defaults_and_save(tmp_path, monkeypatch):
    monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    from backend import settings, storage

    importlib.reload(settings)
    importlib.reload(storage)

    data = storage.load_routes()
    assert "routes" in data
    assert "plugins" in data
    assert "l4_routes" in data

    data["routes"].append({"id": "1"})
    storage.save_routes(data)
    data2 = storage.load_routes()
    assert data2["routes"][0]["id"] == "1"

    raw = json.dumps({"routes": []})
    saved = storage.save_routes_raw(raw)
    assert saved["routes"] == []


def test_validation_helpers():
    from backend import validation

    assert validation.normalize_domains([" Example.COM "]) == ["example.com"]
    assert validation.validate_domain("example.com")
    assert not validation.validate_domain("bad host")

    assert validation.validate_port(80)
    assert not validation.validate_port("nope")

    assert validation.validate_scheme("http")
    assert not validation.validate_scheme("ftp")

    assert validation.validate_path("/ok")
    assert not validation.validate_path("nope")

    assert validation.duration(5) == "5s"
    assert validation.duration("10") == "10s"
    assert validation.duration("1m") == "1m"

    headers = validation.parse_headers(["X-Test: 1", " "])
    assert headers["X-Test"] == "1"
    with pytest.raises(ValueError):
        validation.parse_headers(["badheader"])
    with pytest.raises(ValueError):
        validation.parse_headers([": value"])

    values = validation.parse_header_values(["X-Test: a,b", " "])
    assert values["X-Test"] == ["a", "b"]
    values2 = validation.parse_header_values({"X-Test": "x", "X-List": ["a", " "]})
    assert values2["X-Test"] == ["x"]
    with pytest.raises(ValueError):
        validation.parse_header_values(["X-Test: "])
    with pytest.raises(ValueError):
        validation.parse_header_values(["badheader"])
    with pytest.raises(ValueError):
        validation.parse_header_values([": value"])

    assert validation.duration("   ") is None


def test_validation_route_payload_full():
    from backend import validation

    payload = {
        "domains": ["example.com"],
        "methods": ["", "GET", "POST"],
        "match_headers": ["X-Env: prod"],
        "upstreams": [{"scheme": "https", "host": "up", "port": 443, "weight": 2}],
        "lb_policy": "least_conn",
        "request_body_max_mb": "10",
        "headers_up": ["X-Up: yes"],
        "headers_down": ["X-Down: yes"],
        "response_headers": ["X-Resp: yes"],
        "timeouts": {"connect": 1, "read": 2, "write": 3},
        "health_active": {"path": "/health", "interval": "5", "timeout": "2", "headers": ["X-H: ok"]},
        "health_passive": {"unhealthy_statuses": [500], "max_fails": 2, "fail_duration": "10"},
        "transport": {
            "dial_timeout": "1",
            "read_buffer": 1024,
            "write_buffer": 2048,
            "keepalive": "5",
            "tls_insecure": True,
        },
        "proxy_opts": {"flush_interval": "1", "buffer_requests": True, "buffer_responses": True},
        "redirect": {"location": "https://example.com", "code": 301},
        "path_routes": [
            {
                "path": "/api",
                "strip_prefix": True,
                "upstream": {"host": "up", "port": 8080},
                "methods": ["GET"],
                "match_headers": ["X-P: v"],
                "redirect": {"location": "https://example.com/api", "code": 302},
            },
            {
                "path": "/resp",
                "upstream": {"host": "up", "port": 8081},
                "respond": {"status": 418, "body": "hi", "content_type": "text/plain"},
            },
            {"path": ""},  # should be skipped
        ],
        "options_response": {"enabled": True, "status": 204},
        "rate_limit": {"key": "remote_ip", "window": "10s", "max": 5, "burst": 2},
        "cache_override": {"enabled": True},
        "replace_response": {"find": "a", "replace": "b", "status": 200},
        "webdav": {"enabled": True, "root": "/data", "username": "u", "password": "p", "methods": ["GET"]},
        "realip_override": {"cidrs": ["1.1.1.0/24"]},
        "geoip_override": {"enabled": True},
    }
    out = validation.validate_route_payload(payload)
    assert out["domains"] == ["example.com"]
    assert out["redirect"]["code"] == 301
    assert out["path_routes"][0]["strip_prefix"] is True
    assert out["path_routes"][1]["respond"]["status"] == 418


def test_validation_route_payload_errors():
    from backend import validation

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": []})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["bad host"], "upstream": {"host": "x", "port": 80}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "methods": ["BAD METHOD"], "upstream": {"host": "x", "port": 80}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": "nope"}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "request_body_max_mb": -1})
    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "request_body_max_mb": "bad"})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "timeouts": {"connect": -1}})
    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "timeouts": {"connect": "bad"}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "health_active": {"path": ""}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "health_passive": {"unhealthy_statuses": ["bad"]}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "health_passive": {"unhealthy_statuses": [700]}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "health_passive": {"unhealthy_statuses": [500], "max_fails": 0}})
    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "health_passive": {"unhealthy_statuses": [500], "max_fails": "bad"}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "redirect": {"location": "x", "code": "nope"}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "redirect": {"location": "x", "code": 700}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "respond": {"status": "bad"}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "respond": {"status": 700}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "path_routes": [{"path": "bad"}]})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "path_routes": [{"path": "/ok", "methods": ["BAD METHOD"]}]})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "options_response": {"enabled": True, "status": 700}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "rate_limit": {"max": "bad"}})

    with pytest.raises(ValueError):
        validation.validate_route_payload({"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "rate_limit": {"max": 1, "burst": "bad"}})

    # validate_upstream errors
    with pytest.raises(ValueError):
        validation.validate_upstream({"scheme": "ftp", "host": "x", "port": 80})
    with pytest.raises(ValueError):
        validation.validate_upstream({"scheme": "http", "host": " ", "port": 80})
    with pytest.raises(ValueError):
        validation.validate_upstream({"scheme": "http", "host": "x", "port": 80, "weight": "bad"})
    with pytest.raises(ValueError):
        validation.validate_upstream({"scheme": "http", "host": "x", "port": 80, "weight": 0})

    # rate limit max < 1
    with pytest.raises(ValueError):
        validation.validate_rate_limit({"max": 0})
    with pytest.raises(ValueError):
        validation.validate_rate_limit({"max": "0"})

    # replace_response with no find
    assert validation.validate_replace_response({"replace": "x"}) is None

    # replace_response invalid status
    rep = validation.validate_replace_response({"find": "a", "replace": "b", "status": "bad"})
    assert rep["status"] is None

    # webdav disabled
    assert validation.validate_webdav({"enabled": False}) is None

    # respond valid
    out = validation.validate_route_payload(
        {"domains": ["example.com"], "upstream": {"host": "x", "port": 80}, "respond": {"status": 200, "body": "ok"}}
    )
    assert out["respond"]["status"] == 200

    # health_passive max_fails empty -> None
    out2 = validation.validate_route_payload(
        {
            "domains": ["example.com"],
            "upstream": {"host": "x", "port": 80},
            "health_passive": {"unhealthy_statuses": [500], "max_fails": ""},
        }
    )
    assert out2["health_passive"]["max_fails"] is None

    # path route invalid method with valid upstream
    with pytest.raises(ValueError):
        validation.validate_route_payload(
            {
                "domains": ["example.com"],
                "upstream": {"host": "x", "port": 80},
                "path_routes": [{"path": "/ok", "methods": ["BAD METHOD"], "upstream": {"host": "x", "port": 80}}],
            }
        )
