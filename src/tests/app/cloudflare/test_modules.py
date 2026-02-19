import importlib
import json
import types

import pytest


def test_cf_store_and_configured(tmp_path, monkeypatch, reload_settings):
    from backend.cloudflare.store import TunnelStateStorage
    from backend.cloudflare.hostnames import cf_configured
    import backend.cloudflare.store as store_mod

    state_path = tmp_path / "state.json"
    store = TunnelStateStorage(state_path)
    assert store.get_api_token() is None
    store.set_api_token("tok")
    assert store.get_api_token() == "tok"

    store.upsert_tunnel(name="t1", tunnel_id="id1", tunnel_token="tt", zone="example.com")
    assert store.get_tunnel("t1")["id"] == "id1"
    store.remove_tunnel("t1")
    assert store.get_tunnel("t1") is None

    # corrupted state file
    state_path.write_text("{bad json")
    assert store.load()["tunnels"] == {}

    # empty state file
    state_path.write_text("")
    assert store.load()["tunnels"] == {}

    # non-dict state
    state_path.write_text(json.dumps(["bad"]))
    assert store.load()["tunnels"] == {}

    # tunnels not dict
    state_path.write_text(json.dumps({"api_token": "tok", "tunnels": []}))
    assert store.load()["tunnels"] == {}

    # chmod error
    monkeypatch.setattr(store_mod.os, "chmod", lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
    store.save({"api_token": "tok", "tunnels": {}})

    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.setenv("CLOUDFLARE_STATE_FILE", str(state_path))
    reload_settings()
    # token in state file should mark configured
    state_path.write_text(json.dumps({"api_token": "tok", "tunnels": {}}))
    assert cf_configured() is True
    # invalid state file -> False if no env token
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "")
    reload_settings()
    state_path.write_text(json.dumps({"api_token": "tok", "tunnels": {}}))
    assert cf_configured() is True
    state_path.write_text("{bad")
    assert cf_configured() is False


@pytest.mark.asyncio
async def test_cf_checker_methods(monkeypatch):
    from backend.cloudflare.checker import CloudflareTokenCheckerSDK

    class DummyResp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class DummyZones:
        async def list(self, **kwargs):
            class Page:
                result = []

            return Page()

    class DummyDNSRecords:
        async def create(self, **kwargs):
            class Rec:
                id = "rid"

            return Rec()

        async def delete(self, **kwargs):
            return None

    class DummyDNS:
        records = DummyDNSRecords()

    class DummyClient:
        def __init__(self):
            self._client = self
            self.zones = DummyZones()
            self.dns = DummyDNS()

        async def get(self, *args, **kwargs):
            return DummyResp({"success": True})

        async def post(self, *args, **kwargs):
            return DummyResp({"success": True, "result": {"id": "tid"}})

        async def delete(self, *args, **kwargs):
            return DummyResp({"success": True})

    checker = CloudflareTokenCheckerSDK("tok")
    checker.client = DummyClient()

    ok, data = await checker.verify_token()
    assert ok is True

    zone_id, account_id, ok2, _ = await checker.pick_zone_and_account()
    assert ok2 is False
    assert zone_id is None

    ok3, _ = await checker.dns_canary("zone")
    assert ok3 is True

    ok4, _ = await checker.tunnel_canary("acc")
    assert ok4 is True

    res = await checker.check()
    assert res.ok is True

    # error paths
    class BadClient(DummyClient):
        async def get(self, *args, **kwargs):
            raise RuntimeError("boom")

    checker.client = BadClient()
    ok2, _ = await checker.verify_token()
    assert ok2 is False

    # pick zone with account missing
    class ZoneMissingAccount:
        async def list(self, **kwargs):
            class Zone:
                id = "z"
                account = None

                def to_dict(self):
                    return {}

            class Page:
                result = [Zone()]

            return Page()

    checker.client = DummyClient()
    checker.client.zones = ZoneMissingAccount()
    zone_id, account_id, ok3, _ = await checker.pick_zone_and_account()
    assert zone_id == "z"
    assert ok3 is False

    # pick zone success
    class ZoneOk:
        async def list(self, **kwargs):
            class Zone:
                id = "z"
                account = types.SimpleNamespace(id="a")

                def to_dict(self):
                    return {"id": "z"}

            class Page:
                result = [Zone()]

            return Page()

    checker.client.zones = ZoneOk()
    zone_id2, account_id2, ok4, _ = await checker.pick_zone_and_account()
    assert ok4 is True
    assert account_id2 == "a"

    # pick zone exception
    class ZoneBoom:
        async def list(self, **kwargs):
            raise RuntimeError("boom")

    checker.client.zones = ZoneBoom()
    zone_id3, account_id3, ok5, details = await checker.pick_zone_and_account()
    assert ok5 is False
    assert zone_id3 is None

    # dns_canary error
    class BadDNSRecords:
        async def create(self, **kwargs):
            raise RuntimeError("fail")

    checker.client.dns.records = BadDNSRecords()
    ok4, _ = await checker.dns_canary("zone")
    assert ok4 is False

    # tunnel_canary error
    class BadClient2(DummyClient):
        async def post(self, *args, **kwargs):
            return DummyResp({"success": False})

    checker.client = BadClient2()
    ok5, _ = await checker.tunnel_canary("acc")
    assert ok5 is False

    # tunnel_canary exception
    class BadClient3(DummyClient):
        async def post(self, *args, **kwargs):
            raise RuntimeError("fail")

    checker.client = BadClient3()
    ok6, _ = await checker.tunnel_canary("acc")
    assert ok6 is False


@pytest.mark.asyncio
async def test_cf_hostnames_apply(monkeypatch, tmp_path, cf_env, reload_settings):
    from backend.cloudflare import hostnames

    class DummyCF:
        def __init__(self, state_file):
            self.ready = True

        async def bootstrap(self):
            return False

        async def set_token(self, token, persist=True):
            self.ready = True

        async def resolve_zone_for_hostname(self, hostname):
            return {"zone": "example.com", "zone_id": "z", "account_id": "a"}

        async def provision_all_to_caddy(self, **kwargs):
            return {"zone": kwargs.get("zone"), "tunnel_id": "tid"}

    monkeypatch.setattr(hostnames, "CloudFlare", DummyCF)
    cf_env(CLOUDFLARE_API_TOKEN="token")

    # validate service helpers
    assert hostnames.validate_cf_service("http_status:200") is True
    assert hostnames.validate_cf_service("http_status:bad") is False
    assert hostnames.validate_cf_service("hello_world") is True
    assert hostnames.validate_cf_service("http://x") is True
    assert hostnames.validate_cf_service("bad") is False

    # normalization skips invalid entries
    norm = hostnames._normalize_hostnames({"hostnames": ["bad", {"hostname": ""}]})
    assert norm["hostnames"] == []

    data = {"hostnames": [{"hostname": "demo.example.com", "service": "http://127.0.0.1:80", "enabled": True}]}
    result = await hostnames.apply_cloudflare_config(data)
    assert result["status"] == "ok"

    # load/save hostnames with missing file and fallback
    reload_settings()
    loaded = hostnames.load_cf_hostnames()
    assert loaded["hostnames"] == []
    loaded["fallback"] = ""
    hostnames.save_cf_hostnames(loaded)
    loaded2 = hostnames.load_cf_hostnames()
    assert "fallback" in loaded2

    # load when hostnames file is disabled
    monkeypatch.setattr(hostnames.settings, "CLOUDFLARE_HOSTNAMES_FILE", "")
    loaded3 = hostnames.load_cf_hostnames()
    assert loaded3["hostnames"] == []
    monkeypatch.setattr(hostnames.settings, "CLOUDFLARE_HOSTNAMES_FILE", str(tmp_path / "hostnames.json"))

    # sync hostnames from routes
    routes = {"routes": [{"domains": ["sync.example.com"], "enabled": False}, {"domains": ["bad host"]}]}
    sync = hostnames.sync_cf_hostnames_from_routes(routes)
    assert sync["added"] >= 1
    assert sync["skipped"] >= 1

    # apply with no hostnames
    empty = await hostnames.apply_cloudflare_config({"hostnames": []})
    assert empty["domains"] == 0


@pytest.mark.asyncio
async def test_cf_flow_sync(monkeypatch, tmp_path, cf_env):
    from backend.cloudflare import flow

    class DummyCF:
        def __init__(self, state_file):
            self.ready = True

        async def bootstrap(self):
            return True

        async def set_token(self, token, persist=True):
            self.ready = True

        async def resolve_zone_for_hostname(self, hostname):
            return {"zone": "example.com", "zone_id": "z", "account_id": "a"}

        async def provision_all_to_caddy(self, **kwargs):
            return {"zone": kwargs.get("zone"), "tunnel_id": "tid"}

    monkeypatch.setattr(flow, "CloudFlare", DummyCF)

    cf_env(CLOUDFLARE_API_TOKEN="")

    # no domains
    monkeypatch.setattr(flow, "load_routes", lambda: {"routes": []})
    res = await flow.sync_cloudflare_from_routes()
    assert res["status"] == "ok"

    # with domains + ssh exception
    routes = {
        "routes": [
            {"domains": ["ssh.example.com"], "upstream": {"host": "1.2.3.4", "port": 22}},
            {"domains": ["cname.example.com"], "upstream": {"host": "git.internal", "port": 22}},
            {"domains": ["list.example.com"], "upstreams": [{"host": "10.0.0.2", "port": 22}]},
            {
                "domains": ["path.example.com"],
                "path_routes": [{"upstreams": [{"host": "10.0.0.3", "port": 22}]}],
            },
        ],
        "l4_routes": [
            {
                "listen": ":22",
                "match": {"sni": ["ssh.example.com"]},
                "proxy": {"upstreams": [{"dial": "tcp://10.0.0.1:22"}]},
            },
            {"listen": ":22", "match": {"sni": ["skip.example.com"]}, "proxy": {"upstreams": [{}]}},
            {"listen": ":1234", "proxy": {"upstreams": [{"dial": ""}]}},
        ],
    }
    monkeypatch.setattr(flow, "load_routes", lambda: routes)
    res2 = await flow.sync_cloudflare_from_routes()
    assert res2["status"] == "ok"

    # direct exceptions helper
    exc = flow._extract_ssh_exceptions(routes)
    assert "ssh.example.com" in exc
    assert "cname.example.com" in exc


@pytest.mark.asyncio
async def test_cf_apply_errors(monkeypatch, tmp_path, cf_env):
    from backend.cloudflare import hostnames

    class DummyCF:
        def __init__(self, state_file):
            self.ready = False

        async def bootstrap(self):
            return False

        async def set_token(self, token, persist=True):
            self.ready = False

    monkeypatch.setattr(hostnames, "CloudFlare", DummyCF)
    cf_env(CLOUDFLARE_API_TOKEN="")

    with pytest.raises(hostnames.CloudflareError):
        await hostnames.apply_cloudflare_config({"hostnames": [{"hostname": "x.example.com", "service": "http://x"}]})


@pytest.mark.asyncio
async def test_cf_flow_token_and_skip(monkeypatch, tmp_path, reload_settings):
    from backend.cloudflare import flow

    class DummyCF:
        def __init__(self, state_file, ready=False, bootstrap_value=False):
            self.ready = ready
            self.bootstrap_value = bootstrap_value
            self.tokens = 0

        async def bootstrap(self):
            return self.bootstrap_value

        async def set_token(self, token, persist=True):
            self.tokens += 1
            self.ready = True

        async def resolve_zone_for_hostname(self, hostname):
            raise flow.CloudflareError("boom")

        async def provision_all_to_caddy(self, **kwargs):
            return {"zone": kwargs.get("zone"), "tunnel_id": "tid"}

    monkeypatch.setenv("CLOUDFLARE_STATE_FILE", str(tmp_path / "state.json"))

    created = []

    def factory(ready=False, bootstrap_value=False):
        def _factory(state_file):
            inst = DummyCF(state_file, ready=ready, bootstrap_value=bootstrap_value)
            created.append(inst)
            return inst

        return _factory

    # token branch (set_token called)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    reload_settings()
    monkeypatch.setattr(flow, "CloudFlare", factory(ready=False, bootstrap_value=False))
    monkeypatch.setattr(flow, "load_routes", lambda: {"routes": []})
    res = await flow.sync_cloudflare_from_routes()
    assert res["status"] == "ok"
    assert created[-1].tokens == 1

    # skip when not ready and no token
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "")
    reload_settings()
    monkeypatch.setattr(flow, "CloudFlare", factory(ready=False, bootstrap_value=False))
    res2 = await flow.sync_cloudflare_from_routes()
    assert res2["status"] == "skipped"

    # resolve_zone_for_hostname error should be ignored
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    reload_settings()
    monkeypatch.setattr(flow, "CloudFlare", factory(ready=True, bootstrap_value=True))
    monkeypatch.setattr(flow, "load_routes", lambda: {"routes": [{"domains": ["bad.example.com"]}]})
    res3 = await flow.sync_cloudflare_from_routes()
    assert res3["status"] == "ok"


def test_cf_hostnames_file_and_sync_cases(monkeypatch, tmp_path, cf_env, reload_settings):
    from backend.cloudflare import hostnames
    cf_env(CLOUDFLARE_DEFAULT_SERVICE="bad", CLOUDFLARE_HOSTNAMES_FILE=str(tmp_path / "hn.json"))
    reload_settings()

    assert hostnames.cf_default_fallback() == "http_status:404"

    # file exists but missing hostnames/fallback
    (tmp_path / "hn.json").write_text("{}")
    loaded = hostnames.load_cf_hostnames()
    assert loaded["hostnames"] == []
    assert loaded["fallback"] == "http_status:404"

    # sync should update existing
    hostnames.save_cf_hostnames(
        {"hostnames": [{"hostname": "sync.example.com", "service": "http://x", "enabled": True}]}
    )
    routes = {"routes": [{"domains": ["sync.example.com"], "enabled": False}]}
    res = hostnames.sync_cf_hostnames_from_routes(routes)
    assert res["updated"] == 1


@pytest.mark.asyncio
async def test_cf_hostnames_apply_edge_cases(monkeypatch, tmp_path, cf_env, reload_settings):
    from backend.cloudflare import hostnames

    class DummyCF:
        def __init__(self, state_file, bootstrap_value=False):
            self.ready = True
            self.bootstrap_value = bootstrap_value
            self.set_tokens = 0
            self.calls = []

        async def bootstrap(self):
            return self.bootstrap_value

        async def set_token(self, token, persist=True):
            self.set_tokens += 1
            self.ready = True

        async def resolve_zone_for_hostname(self, hostname):
            if hostname == "bad.example.com":
                raise hostnames.CloudflareError("bad")
            return {"zone": "example.com", "zone_id": "z", "account_id": "a"}

        async def provision_all_to_caddy(self, **kwargs):
            self.calls.append(kwargs)
            return {"zone": kwargs.get("zone"), "tunnel_id": "tid"}

    cf_env(CLOUDFLARE_API_TOKEN="token", CLOUDFLARE_DEFAULT_SERVICE="bad")
    reload_settings()

    # exceptions from routes (port 22)
    monkeypatch.setattr(
        hostnames,
        "load_routes",
        lambda: {"routes": [{"domains": ["ok.example.com"], "upstream": {"host": "1.1.1.1", "port": 22}}]},
    )

    created = []

    def factory(bootstrap_value):
        def _factory(state_file):
            inst = DummyCF(state_file, bootstrap_value=bootstrap_value)
            created.append(inst)
            return inst

        return _factory

    # invalid fallback is reset; resolve error is skipped; exceptions are passed
    monkeypatch.setattr(hostnames, "CloudFlare", factory(False))
    result = await hostnames.apply_cloudflare_config(
        {
            "fallback": "bad",
            "hostnames": [
                {"hostname": "ok.example.com", "service": "http://127.0.0.1:80", "enabled": True},
                {"hostname": "bad.example.com", "service": "http://127.0.0.1:80", "enabled": True},
            ],
        }
    )
    assert result["status"] == "ok"
    inst = created[-1]
    assert inst.set_tokens == 1
    assert inst.calls[0]["fallback_service"] == "http_status:404"
    assert inst.calls[0]["dns_exceptions"]

    # bootstrap True should skip set_token
    monkeypatch.setattr(hostnames, "CloudFlare", factory(True))
    await hostnames.apply_cloudflare_config(
        {"hostnames": [{"hostname": "ok.example.com", "service": "http://127.0.0.1:80"}]}
    )
    inst2 = created[-1]
    assert inst2.set_tokens == 0
