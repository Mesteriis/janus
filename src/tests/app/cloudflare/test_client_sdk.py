import asyncio
import importlib
import json
import sys
import types
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_cloudflare_client_core(monkeypatch, tmp_path):
    from app.cloudflare import client as cf_client
    from app.cloudflare.checker import TokenCheckResult

    class DummyChecker:
        def __init__(self, token):
            self.token = token

        async def check(self):
            return TokenCheckResult(
                ok=True,
                token_active=True,
                can_list_zones=False,
                can_edit_dns=False,
                can_tunnel_rw=False,
                chosen_zone_id="z",
                chosen_account_id="a",
                details={},
            )

    class DummyResp:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code
            self.text = json.dumps(payload)

        def json(self):
            return self._payload

    class DummyHTTP:
        async def request(self, method, path, headers=None, json=None):
            return DummyResp({"success": True, "result": []})

    class DummyZones:
        async def list(self, **kwargs):
            class Page:
                def __init__(self):
                    self.result = []

            return Page()

    class DummyDNSRecords:
        def __init__(self):
            self._records = []

        async def list(self, **kwargs):
            class Page:
                def __init__(self, result):
                    self.result = result

            return Page(self._records)

        async def update(self, **kwargs):
            return None

        async def create(self, **kwargs):
            return None

    class DummyDNS:
        def __init__(self):
            self.records = DummyDNSRecords()

    class DummyAsyncCF:
        def __init__(self, api_token):
            self._client = DummyHTTP()
            self.zones = DummyZones()
            self.dns = DummyDNS()

    monkeypatch.setattr(cf_client, "CloudflareTokenCheckerSDK", DummyChecker)
    monkeypatch.setattr(cf_client, "AsyncCloudflare", DummyAsyncCF)

    state = tmp_path / "state.json"
    cf = cf_client.CloudFlare(state_file=state)
    assert cf.gen_token_url().startswith("https://")

    # bootstrap no token
    assert await cf.bootstrap() is False

    # bootstrap with bad token
    cf2 = cf_client.CloudFlare(state_file=tmp_path / "state2.json")
    cf2._state.set_api_token("tok")

    async def bad_set_token(token, persist=True):
        raise RuntimeError("bad")

    monkeypatch.setattr(cf2, "set_token", bad_set_token)
    assert await cf2.bootstrap() is False

    # set_token invalid
    class BadChecker:
        def __init__(self, token):
            self.token = token

        async def check(self):
            return TokenCheckResult(
                ok=False,
                token_active=False,
                can_list_zones=False,
                can_edit_dns=False,
                can_tunnel_rw=False,
                chosen_zone_id=None,
                chosen_account_id=None,
                details={"err": "bad"},
            )

    monkeypatch.setattr(cf_client, "CloudflareTokenCheckerSDK", BadChecker)
    cf3 = cf_client.CloudFlare(state_file=tmp_path / "state3.json")
    with pytest.raises(cf_client.CloudflareError):
        await cf3.set_token("tok")

    # restore good checker
    monkeypatch.setattr(cf_client, "CloudflareTokenCheckerSDK", DummyChecker)
    await cf.set_token("tok", persist=True)
    assert cf.ready is True

    # bootstrap success with stored token
    cf5 = cf_client.CloudFlare(state_file=tmp_path / "state5.json")
    cf5._state.set_api_token("tok")
    assert await cf5.bootstrap() is True

    # ensure_ready
    cf4 = cf_client.CloudFlare(state_file=tmp_path / "state4.json")
    with pytest.raises(RuntimeError):
        cf4.ensure_ready()

    # _raw success
    res = await cf._raw("GET", "/x")
    assert res["success"] is True

    # _raw non-json error
    class BadHTTP:
        async def request(self, method, path, headers=None, json=None):
            class Resp:
                status_code = 500
                text = "oops"

                def json(self):
                    raise ValueError("bad")

            return Resp()

    cf._cf._client = BadHTTP()
    with pytest.raises(cf_client.CloudflareError):
        await cf._raw("GET", "/bad")

    # _raw success false
    class FailHTTP:
        async def request(self, method, path, headers=None, json=None):
            return DummyResp({"success": False, "errors": [{"message": "err"}]}, status_code=400)

    cf._cf._client = FailHTTP()
    with pytest.raises(cf_client.CloudflareError):
        await cf._raw("GET", "/bad2")

    # _raw non-dict
    class ListHTTP:
        async def request(self, method, path, headers=None, json=None):
            class Resp:
                status_code = 200

                def json(self):
                    return ["bad"]

            return Resp()

    cf._cf._client = ListHTTP()
    with pytest.raises(cf_client.CloudflareError):
        await cf._raw("GET", "/bad3")


@pytest.mark.asyncio
async def test_cloudflare_client_dns_and_tunnel(monkeypatch, tmp_path):
    from app.cloudflare import client as cf_client
    from app.cloudflare.checker import TokenCheckResult

    class DummyChecker:
        def __init__(self, token):
            self.token = token

        async def check(self):
            return TokenCheckResult(
                ok=True,
                token_active=True,
                can_list_zones=False,
                can_edit_dns=False,
                can_tunnel_rw=False,
                chosen_zone_id="z",
                chosen_account_id="a",
                details={},
            )

    class DummyResp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class DummyHTTP:
        def __init__(self):
            self.calls = []

        async def request(self, method, path, headers=None, json=None):
            self.calls.append((method, path, json))
            if "configurations" in path and method == "GET":
                return DummyResp({"success": True, "result": {"config": {"ingress": []}}})
            if "configurations" in path and method == "PUT":
                return DummyResp({"success": True})
            if path.endswith("/cfd_tunnel") and method == "GET":
                return DummyResp({"success": True, "result": [{"id": "tid", "name": "t1", "token": "tt"}]})
            if path.endswith("/cfd_tunnel") and method == "POST":
                return DummyResp({"success": True, "result": {"id": "tid", "name": "t1", "token": "tt"}})
            return DummyResp({"success": True, "result": []})

    class DummyZones:
        def __init__(self):
            self.with_account = True

        async def list(self, **kwargs):
            class Zone:
                def __init__(self, with_account: bool):
                    self.id = "z1"
                    self.account = types.SimpleNamespace(id="a1") if with_account else None

            class Page:
                def __init__(self, zone):
                    self.result = [zone] if zone else []

            if kwargs.get("name") == "missing.example":
                return Page(None)
            return Page(Zone(self.with_account))

    class DummyDNSRecords:
        def __init__(self):
            self.updated = 0
            self.created = 0
            self._records = [types.SimpleNamespace(id="r1")]

        async def list(self, **kwargs):
            class Page:
                def __init__(self, result):
                    self.result = result

            return Page(self._records)

        async def update(self, **kwargs):
            self.updated += 1

        async def create(self, **kwargs):
            self.created += 1

    class DummyDNS:
        def __init__(self):
            self.records = DummyDNSRecords()

    class DummyAsyncCF:
        def __init__(self, api_token):
            self._client = DummyHTTP()
            self.zones = DummyZones()
            self.dns = DummyDNS()

    monkeypatch.setattr(cf_client, "CloudflareTokenCheckerSDK", DummyChecker)
    monkeypatch.setattr(cf_client, "AsyncCloudflare", DummyAsyncCF)

    cf = cf_client.CloudFlare(state_file=tmp_path / "state.json")
    await cf.set_token("tok", persist=False)

    # _dns_upsert updates existing
    await cf._dns_upsert(zone_id="z1", record_type="A", name="x", content="1.1.1.1", proxied=True)
    # _dns_upsert create
    cf._cf.dns.records._records = []
    await cf._dns_upsert(zone_id="z1", record_type="A", name="y", content="1.1.1.1", proxied=True)

    # list_tunnels
    tunnels = await cf.list_tunnels(account_id="a1")
    assert isinstance(tunnels, list)

    # get_or_create_tunnel (create)
    t = await cf.get_or_create_tunnel(name="t1", account_id="a1")
    assert t["id"] == "tid"

    # get_or_create_tunnel (state hit)
    cf._state.upsert_tunnel(name="t2", tunnel_id="tid2", tunnel_token=None)
    async def _exists(_tid, account_id):
        return True

    monkeypatch.setattr(cf, "_tunnel_exists", _exists)
    t2 = await cf.get_or_create_tunnel(name="t2", account_id="a1")
    assert t2["id"] == "tid2"

    # get_or_create_tunnel (state miss, list by name)
    async def _no(_tid, account_id):
        return False

    monkeypatch.setattr(cf, "_tunnel_exists", _no)
    cf._state.upsert_tunnel(name="t3", tunnel_id="tid3", tunnel_token=None)
    async def list_tunnels(account_id):
        return [{"id": "tidlist", "name": "t3"}]

    monkeypatch.setattr(cf, "list_tunnels", list_tunnels)
    t3 = await cf.get_or_create_tunnel(name="t3", account_id="a1")
    assert t3["id"] == "tidlist"

    # ensure_ingress_for_zone normal path
    res = await cf.ensure_ingress_for_zone(
        account_id="a1",
        tunnel_id="tid",
        zone="example.com",
        service="http://caddy",
        tunnel_name="t1",
        extra_ingress=[{"hostname": "backend.example.com", "service": "http://app"}],
        fallback_service="http_status:404",
    )
    assert res["tunnel_id"] == "tid"

    # ensure_ingress_for_zone self-heal
    async def raw_fail(method, path, payload=None):
        if method == "GET":
            raise cf_client.CloudflareError({"errors": [{"message": "Tunnel not found"}]})
        return {"success": True}

    async def raw_ok(method, path, payload=None):
        return {"success": True}

    cf._raw = raw_fail  # type: ignore[assignment]
    async def create_tunnel(name, account_id):
        return {"id": "newid", "token": "t"}

    monkeypatch.setattr(cf, "get_or_create_tunnel", create_tunnel)
    cf._raw = raw_fail  # first GET fails
    res2 = await cf.ensure_ingress_for_zone(
        account_id="a1",
        tunnel_id="badid",
        zone="example.com",
        service="http://caddy",
        tunnel_name="t1",
        fallback_service="http_status:404",
    )
    assert res2["recreated"] is True

    # ensure_ingress_for_zone raises on other errors
    async def raw_other(method, path, payload=None):
        raise cf_client.CloudflareError({"errors": [{"message": "Other"}]})

    cf._raw = raw_other  # type: ignore[assignment]
    with pytest.raises(cf_client.CloudflareError):
        await cf.ensure_ingress_for_zone(
            account_id="a1",
            tunnel_id="badid",
            zone="example.com",
            service="http://caddy",
            tunnel_name="t1",
        )

    # resolve_zone_for_hostname
    info = await cf.resolve_zone_for_hostname("backend.example.com")
    assert info["zone"] in ("example.com", "backend.example.com")

    # resolve_zone_for_hostname invalid
    with pytest.raises(cf_client.CloudflareError):
        await cf.resolve_zone_for_hostname("bad")

    # _resolve_zone not found
    with pytest.raises(cf_client.CloudflareError):
        await cf._resolve_zone("missing.example")

    # _resolve_zone missing account id
    cf._cf.zones.with_account = False
    with pytest.raises(cf_client.CloudflareError):
        await cf._resolve_zone("example.com")


@pytest.mark.asyncio
async def test_provision_all_to_caddy(monkeypatch, tmp_path):
    from app.cloudflare import client as cf_client
    from app.cloudflare.checker import TokenCheckResult
    from app.cloudflare.constants import DnsException

    class DummyChecker:
        def __init__(self, token):
            self.token = token

        async def check(self):
            return TokenCheckResult(
                ok=True,
                token_active=True,
                can_list_zones=False,
                can_edit_dns=False,
                can_tunnel_rw=False,
                chosen_zone_id="z",
                chosen_account_id="a",
                details={},
            )

    class DummyZones:
        async def list(self, **kwargs):
            class Zone:
                def __init__(self):
                    self.id = "z1"
                    self.account = types.SimpleNamespace(id="a1")

            class Page:
                result = [Zone()]

            return Page()

    class DummyDNSRecords:
        async def list(self, **kwargs):
            class Page:
                result = []

            return Page()

        async def update(self, **kwargs):
            return None

        async def create(self, **kwargs):
            return None

    class DummyDNS:
        def __init__(self):
            self.records = DummyDNSRecords()

    class DummyHTTP:
        async def request(self, method, path, headers=None, json=None):
            if "configurations" in path and method == "GET":
                return types.SimpleNamespace(json=lambda: {"success": True, "result": {"config": {"ingress": []}}})
            if path.endswith("/cfd_tunnel") and method == "GET":
                return types.SimpleNamespace(json=lambda: {"success": True, "result": []})
            return types.SimpleNamespace(json=lambda: {"success": True, "result": {"id": "tid", "token": "tt"}})

    class DummyAsyncCF:
        def __init__(self, api_token):
            self._client = DummyHTTP()
            self.zones = DummyZones()
            self.dns = DummyDNS()

    monkeypatch.setattr(cf_client, "CloudflareTokenCheckerSDK", DummyChecker)
    monkeypatch.setattr(cf_client, "AsyncCloudflare", DummyAsyncCF)

    cf = cf_client.CloudFlare(state_file=tmp_path / "state.json")
    await cf.set_token("tok", persist=False)

    res = await cf.provision_all_to_caddy(
        zone="example.com",
        caddy_url="http://caddy",
        dns_exceptions=[DnsException(fqdn="ssh.example.com", record_type="A", content="1.2.3.4")],
        create_separate_tunnel=True,
        fallback_service="http_status:404",
    )
    assert res["zone"] == "example.com"


@pytest.mark.asyncio
async def test_cloudflare_client_branches(monkeypatch, tmp_path):
    from app.cloudflare import client as cf_client
    from app.cloudflare.checker import TokenCheckResult
    from app.cloudflare.constants import DnsException

    class DummyChecker:
        def __init__(self, token):
            self.token = token

        async def check(self):
            return TokenCheckResult(
                ok=True,
                token_active=True,
                can_list_zones=False,
                can_edit_dns=False,
                can_tunnel_rw=False,
                chosen_zone_id="z",
                chosen_account_id="a",
                details={},
            )

    class DummyZones:
        async def list(self, **kwargs):
            class Zone:
                def __init__(self):
                    self.id = "z1"
                    self.account = types.SimpleNamespace(id="a1")

            class Page:
                result = [Zone()]

            return Page()

    class DummyDNSRecords:
        async def list(self, **kwargs):
            class Page:
                result = []

            return Page()

        async def update(self, **kwargs):
            return None

        async def create(self, **kwargs):
            return None

    class DummyDNS:
        def __init__(self):
            self.records = DummyDNSRecords()

    class DummyHTTP:
        async def request(self, method, path, headers=None, json=None):
            if method == "GET":
                return types.SimpleNamespace(json=lambda: {"success": True, "result": {"config": {"ingress": []}}})
            return types.SimpleNamespace(json=lambda: {"success": True, "result": {"id": "tid", "token": "tt"}})

    class DummyAsyncCF:
        def __init__(self, api_token):
            self._client = DummyHTTP()
            self.zones = DummyZones()
            self.dns = DummyDNS()

    monkeypatch.setattr(cf_client, "CloudflareTokenCheckerSDK", DummyChecker)
    monkeypatch.setattr(cf_client, "AsyncCloudflare", DummyAsyncCF)

    cf = cf_client.CloudFlare(state_file=tmp_path / "state.json")
    await cf.set_token("tok", persist=False)

    # _tunnel_exists true/false
    async def raw(method, path, payload=None):
        if path.endswith("/exist"):
            return {"success": True}
        raise cf_client.CloudflareError({"errors": [{"message": "nope"}]})

    cf._raw = raw  # type: ignore[assignment]
    assert await cf._tunnel_exists("exist", account_id="a1") is True
    assert await cf._tunnel_exists("missing", account_id="a1") is False

    # get_or_create_tunnel create branch
    async def list_empty(account_id):
        return []

    async def raw_create(method, path, payload=None):
        return {"success": True, "result": {"id": "tid", "token": "tt"}}

    cf.list_tunnels = list_empty  # type: ignore[assignment]
    cf._raw = raw_create  # type: ignore[assignment]
    created = await cf.get_or_create_tunnel(name="new", account_id="a1")
    assert created["id"] == "tid"

    # ensure_ingress_for_zone build_ingress branches
    async def raw_cfg(method, path, payload=None):
        if method == "GET":
            return {"success": True, "result": {"config": {"ingress": [{"hostname": "dup.example.com", "service": "x"}]}}}
        return {"success": True}

    cf._raw = raw_cfg  # type: ignore[assignment]
    res = await cf.ensure_ingress_for_zone(
        account_id="a1",
        tunnel_id="tid",
        zone="example.com",
        service="http://caddy",
        tunnel_name="t1",
        extra_ingress=[
            {"hostname": "", "service": "x"},
            {"hostname": "example.com", "service": "http://caddy"},
            {"hostname": "example.com", "service": "http://caddy"},
        ],
        fallback_service="http_status:404",
    )
    assert res["recreated"] is False

    # ensure_ingress_for_zone error message parsing
    async def raw_bad(method, path, payload=None):
        raise cf_client.CloudflareError("boom")

    cf._raw = raw_bad  # type: ignore[assignment]
    with pytest.raises(cf_client.CloudflareError):
        await cf.ensure_ingress_for_zone(
            account_id="a1",
            tunnel_id="tid",
            zone="example.com",
            service="http://caddy",
            tunnel_name="t1",
        )

    # provision_all_to_caddy default tunnel name (create_separate_tunnel False)
    async def _resolve_zone(zone):
        return {"zone_id": "z1", "account_id": "a1"}

    cf._resolve_zone = _resolve_zone  # type: ignore[assignment]
    async def get_or_create(name, account_id):
        return {"id": "tid", "token": "tt"}

    cf.get_or_create_tunnel = get_or_create  # type: ignore[assignment]
    async def ensure_ingress(**kwargs):
        return {"tunnel_id": "tid", "recreated": False}

    async def dns_upsert(**kwargs):
        return None

    cf.ensure_ingress_for_zone = ensure_ingress  # type: ignore[assignment]
    cf._dns_upsert = dns_upsert  # type: ignore[assignment]
    res2 = await cf.provision_all_to_caddy(
        zone="example.com",
        caddy_url="http://caddy",
        dns_exceptions=[DnsException(fqdn="a.example.com", record_type="A", content="1.1.1.1")],
        create_separate_tunnel=False,
    )
    assert res2["tunnel_name"]

    # _resolve_zone cache
    cf._zone_cache["example.com"] = {"zone_id": "z1", "account_id": "a1"}
    cached = await cf_client.CloudFlare._resolve_zone(cf, "example.com")
    assert cached["zone_id"] == "z1"

    # resolve_zone_for_hostname not found
    async def _resolve_raise(zone):
        raise cf_client.CloudflareError("no")

    cf._resolve_zone = _resolve_raise  # type: ignore[assignment]
    with pytest.raises(cf_client.CloudflareError):
        await cf.resolve_zone_for_hostname("a.b.example")


def test_sdk_import_paths(monkeypatch, tmp_path):
    import app.cloudflare.sdk as sdk
    import importlib
    import os

    local_root = (Path(sdk.__file__).resolve().parent.parent)
    # Make cwd and sys.path include local_root + empty entries to exercise removal
    cwd = os.getcwd()
    os.chdir(local_root)
    sys.path.insert(0, "")
    sys.path.insert(0, "")
    sys.path.insert(0, str(local_root))

    try:
        # Force reload with dummy module having AsyncCloudflare and __file__ in local package
        dummy = types.SimpleNamespace(AsyncCloudflare=object, __file__=str(local_root / "cloudflare" / "__init__.py"))
        monkeypatch.setitem(sys.modules, "cloudflare", dummy)
        importlib.reload(sdk)
        assert sdk.AsyncCloudflare is not None

        # Reload with only Cloudflare (fallback path)
        class Sync:
            def __init__(self, api_token):
                self._client = object()
                self.zones = object()
                self.dns = object()

        dummy2 = types.SimpleNamespace(Cloudflare=Sync, __file__="dummy.py")
        monkeypatch.setitem(sys.modules, "cloudflare", dummy2)
        importlib.reload(sdk)
        assert hasattr(sdk, "AsyncCloudflare")

        # Instantiate fallback to cover __init__
        sdk.AsyncCloudflare(api_token="tok")
    finally:
        os.chdir(cwd)

    # _Asyncify callable and nested
    class Obj:
        def __init__(self):
            self.val = 0
            self.child = types.SimpleNamespace(x=1)

        def inc(self, x):
            self.val += x
            return self.val

    asyncify = sdk._Asyncify(Obj())
    asyncio.run(asyncify.inc(1))
    assert asyncify._obj.val == 1
    assert asyncify.val == 1
    assert hasattr(asyncify.child, "_obj")


def test_sdk_import_error(monkeypatch):
    import importlib
    import app.cloudflare.sdk as sdk

    dummy = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "cloudflare", dummy)
    with pytest.raises(ImportError):
        importlib.reload(sdk)


def test_sdk_import_path_exceptions(monkeypatch, tmp_path):
    import importlib
    import os
    import pathlib
    import app.cloudflare.sdk as sdk

    local_root = Path(sdk.__file__).resolve().parent.parent
    cwd = os.getcwd()
    sys.path.insert(0, "")
    sys.path.insert(0, "boom")

    orig_resolve = pathlib.Path.resolve

    def bad_resolve(self):
        if str(self) == "boom":
            raise RuntimeError("boom")
        return orig_resolve(self)

    try:
        monkeypatch.setattr("pathlib.Path.cwd", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr("pathlib.Path.resolve", bad_resolve)
        dummy = types.SimpleNamespace(AsyncCloudflare=object, __file__="boom")
        monkeypatch.setitem(sys.modules, "cloudflare", dummy)
        os.chdir(local_root)
        importlib.reload(sdk)
        assert sdk.AsyncCloudflare is not None
    finally:
        os.chdir(cwd)
        while "" in sys.path:
            sys.path.remove("")
        while "boom" in sys.path:
            sys.path.remove("boom")
