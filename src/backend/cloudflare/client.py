from __future__ import annotations

import warnings


warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
    category=UserWarning,
)
from .store import TunnelStateStorage

import ipaddress
import json
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote

from .sdk import AsyncCloudflare

from .checker import CloudflareTokenCheckerSDK
from .constants import PERMISSIONS, TOKEN_NAME, DnsException
from .exception import CloudflareError


class CloudFlare:
    """
    Финальный Cloudflare client (self-healing).

    - State в JSON: api_token + tunnels
    - DNS через SDK
    - Tunnel API через raw (SDK не покрывает полностью)
    - Reuse туннеля по умолчанию
    - Опционально отдельные туннели по имени
    - Self-healing:
        * если туннель удалили / конфиг не найден -> пересоздаём и повторяем один раз
    """

    DEFAULT_TUNNEL_NAME = "pve-main"

    def __init__(self, *, state_file: Path):
        self._state = TunnelStateStorage(state_file)

        self._token: Optional[str] = None
        self._cf: Optional[AsyncCloudflare] = None
        self._zone_id: Optional[str] = None
        self._account_id: Optional[str] = None
        self._zone_cache: dict[str, dict[str, str]] = {}

        self.ready: bool = False

    # ------------------------------------------------------
    # Token deeplink
    # ------------------------------------------------------

    @staticmethod
    def gen_token_url() -> str:
        base = "https://dash.cloudflare.com/profile/api-tokens"
        params = {
            "permissionGroupKeys": quote(json.dumps(PERMISSIONS, separators=(",", ":"))),
            "name": quote(str(TOKEN_NAME)),
            "accountId": "*",
            "zoneId": "all",
        }
        return f"{base}?" + "&".join(f"{k}={v}" for k, v in params.items())

    # ------------------------------------------------------
    # Bootstrap / token init
    # ------------------------------------------------------

    async def bootstrap(self) -> bool:
        token = self._state.get_api_token()
        if not token:
            return False

        try:
            await self.set_token(token, persist=False)
            return True
        except Exception as _:
            self.ready = False
            return False

    async def set_token(self, token: str, *, persist: bool = True) -> None:
        checker = CloudflareTokenCheckerSDK(token)
        res = await checker.check()
        if not res.ok:
            raise CloudflareError(f"Invalid token: {res.details}")

        self._token = token
        self._zone_id = res.chosen_zone_id
        self._account_id = res.chosen_account_id
        self._cf = AsyncCloudflare(api_token=token)
        self.ready = True

        if persist:
            self._state.set_api_token(token)

    def ensure_ready(self) -> None:
        if not self.ready or not self._cf:
            raise RuntimeError("CloudFlare client is not ready")

    # ------------------------------------------------------
    # Raw helper
    # ------------------------------------------------------

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _raw(self, method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
        self.ensure_ready()
        r = await self._cf._client.request(
            method,
            path,
            headers=self._headers,
            json=payload,
        )
        try:
            data = r.json()
        except Exception:
            raise CloudflareError(
                {
                    "success": False,
                    "status": getattr(r, "status_code", None),
                    "errors": [{"message": getattr(r, "text", "") or "Non-JSON response"}],
                }
            )
        if not isinstance(data, dict):
            raise CloudflareError(
                {
                    "success": False,
                    "status": getattr(r, "status_code", None),
                    "errors": [{"message": "Invalid JSON response"}],
                    "raw": data,
                }
            )
        if not data.get("success"):
            # сохраняем оригинальный ответ CF, чтобы по коду/сообщению лечить кейсы
            raise CloudflareError(data)
        return data

    # ======================================================
    # DNS (SDK)
    # ======================================================

    async def _dns_upsert(
        self,
        *,
        zone_id: str,
        record_type: str,
        name: str,
        content: str,
        proxied: bool,
    ) -> None:
        self.ensure_ready()
        cf = self._cf

        found = await cf.dns.records.list(
            zone_id=zone_id,
            type=record_type,
            name=name,
            per_page=100,
            page=1,
        )

        if found.result:
            for rec in found.result:
                await cf.dns.records.update(
                    zone_id=zone_id,
                    dns_record_id=rec.id,
                    type=record_type,
                    name=name,
                    content=content,
                    proxied=proxied,
                    ttl=120,
                )
            return

        await cf.dns.records.create(
            zone_id=zone_id,
            type=record_type,
            name=name,
            content=content,
            proxied=proxied,
            ttl=120,
        )

    async def list_tunnels(self, *, account_id: str) -> list[dict]:
        data = await self._raw("GET", f"/accounts/{account_id}/cfd_tunnel")
        return data.get("result", [])

    async def _tunnel_exists(self, tunnel_id: str, *, account_id: str) -> bool:
        try:
            await self._raw("GET", f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}")
            return True
        except CloudflareError:
            return False

    async def get_or_create_tunnel(self, *, name: str, account_id: str) -> dict[str, Any]:
        # 1) state -> verify exists
        saved = self._state.get_tunnel(name)
        if saved:
            if await self._tunnel_exists(saved["id"], account_id=account_id):
                return saved
            self._state.remove_tunnel(name)

        # 2) cloudflare list by name
        for t in await self.list_tunnels(account_id=account_id):
            if t.get("name") == name:
                self._state.upsert_tunnel(name=name, tunnel_id=t["id"], tunnel_token=None)
                return t

        # 3) create
        data = await self._raw(
            "POST",
            f"/accounts/{account_id}/cfd_tunnel",
            {"name": name, "config_src": "cloudflare"},
        )
        t = data["result"]
        self._state.upsert_tunnel(name=name, tunnel_id=t["id"], tunnel_token=t.get("token"))
        return t

    async def ensure_ingress_for_zone(
        self,
        *,
        account_id: str,
        tunnel_id: str,
        zone: str,
        service: str,
        tunnel_name: str,
        extra_ingress: Iterable[dict[str, str]] = (),
        fallback_service: str = "http_status:404",
    ) -> dict[str, Any]:
        """
        Merge ingress rules for:
          zone
          *.zone
        and ensure fallback.

        Self-heal:
          - if tunnel not found / config not found -> recreate tunnel and retry once
        """
        def build_ingress(existing: list[dict]) -> list[dict]:
            desired = {
                zone: service,
                f"*.{zone}": service,
            }
            ordered: list[dict] = []
            seen: set[str] = set()

            for item in extra_ingress or []:
                hostname = (item.get("hostname") or "").strip().lower()
                if not hostname:
                    continue
                svc = (item.get("service") or "").strip() or service
                if hostname in seen:
                    continue
                ordered.append({"hostname": hostname, "service": svc})
                seen.add(hostname)

            for hostname in (zone, f"*.{zone}"):
                if hostname in seen:
                    continue
                ordered.append({"hostname": hostname, "service": desired[hostname]})
                seen.add(hostname)

            current = [
                r
                for r in (existing or [])
                if r.get("hostname") not in desired and r.get("service") != fallback_service
            ]
            current = ordered + current

            if not any(r.get("service") == fallback_service for r in current):
                current.append({"service": fallback_service})

            return current

        # ---- try #1
        try:
            cfg = await self._raw(
                "GET",
                f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
            )
            ingress = cfg.get("result", {}).get("config", {}).get("ingress", []) or []
            ingress = build_ingress(ingress)

            await self._raw(
                "PUT",
                f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
                {"config": {"ingress": ingress}},
            )
            return {"tunnel_id": tunnel_id, "recreated": False}

        except CloudflareError as e:
            data = e.args[0] if e.args else {}
            msg = ""
            try:
                msg = (data.get("errors") or [{}])[0].get("message", "")
            except Exception:
                msg = str(e)

            if msg not in ("Tunnel not found", "Configuration for tunnel not found"):
                raise

        # ---- try #2: self-heal recreate and retry once
        print("⚠️ Tunnel not found, recreating…")

        self._state.remove_tunnel(tunnel_name)
        tunnel = await self.get_or_create_tunnel(name=tunnel_name, account_id=account_id)
        new_id = tunnel["id"]

        ingress = build_ingress([])
        await self._raw(
            "PUT",
            f"/accounts/{account_id}/cfd_tunnel/{new_id}/configurations",
            {"config": {"ingress": ingress}},
        )
        return {"tunnel_id": new_id, "recreated": True}

    # ======================================================
    # Orchestration
    # ======================================================

    async def provision_all_to_caddy(
        self,
        *,
        zone: str,
        caddy_url: str = "http://caddy:80",
        dns_exceptions: Iterable[DnsException] = (),
        tunnel_name: Optional[str] = None,
        create_separate_tunnel: bool = False,
        extra_ingress: Iterable[dict[str, str]] = (),
        fallback_service: str = "http_status:404",
    ) -> dict[str, Any]:
        """
        zone = корневой домен (например domsub.me)

        По умолчанию:
          - reuse DEFAULT_TUNNEL_NAME (один туннель на много доменов)

        Опционально:
          - отдельный туннель для зоны:
                create_separate_tunnel=True
                tunnel_name="pve-sh-inc"
            или (если имя не задано) авто: pve-main-<zone>
        """
        self.ensure_ready()

        zone = zone.strip().lower()
        zone_info = await self._resolve_zone(zone)
        zone_id = zone_info["zone_id"]
        account_id = zone_info["account_id"]

        if create_separate_tunnel:
            name = tunnel_name or f"{self.DEFAULT_TUNNEL_NAME}-{zone}"
        else:
            name = tunnel_name or self.DEFAULT_TUNNEL_NAME

        tunnel = await self.get_or_create_tunnel(name=name, account_id=account_id)
        tunnel_id = tunnel["id"]

        ingress_res = await self.ensure_ingress_for_zone(
            account_id=account_id,
            tunnel_id=tunnel_id,
            zone=zone,
            service=caddy_url,
            tunnel_name=name,
            extra_ingress=extra_ingress,
            fallback_service=fallback_service,
        )
        tunnel_id = ingress_res["tunnel_id"]

        target = f"{tunnel_id}.cfargotunnel.com"
        await self._dns_upsert(zone_id=zone_id, record_type="CNAME", name=zone, content=target, proxied=True)
        await self._dns_upsert(zone_id=zone_id, record_type="CNAME", name=f"*.{zone}", content=target, proxied=True)

        for exc in dns_exceptions:
            if exc.record_type.upper() in ("A", "AAAA"):
                ipaddress.ip_address(exc.content)

            await self._dns_upsert(
                zone_id=zone_id,
                record_type=exc.record_type,
                name=exc.fqdn,
                content=exc.content,
                proxied=False,
            )

        # Persist to state (also adds zone to list)
        self._state.upsert_tunnel(
            name=name,
            tunnel_id=tunnel_id,
            tunnel_token=tunnel.get("token"),  # может быть None если tunnel был найден/реюзнут
            zone=zone,
        )

        return {
            "tunnel_name": name,
            "tunnel_id": tunnel_id,
            "zone": zone,
            "recreated": ingress_res.get("recreated", False),
        }

    async def _resolve_zone(self, zone: str) -> dict[str, str]:
        zone = zone.strip().lower()
        cached = self._zone_cache.get(zone)
        if cached:
            return cached

        self.ensure_ready()
        page = await self._cf.zones.list(name=zone, per_page=1, page=1)
        if not page.result:
            raise CloudflareError({"success": False, "errors": [{"message": f"Zone not found: {zone}"}]})
        z = page.result[0]
        zone_id = z.id
        account_id = getattr(z.account, "id", None) if z.account else None
        if not account_id:
            raise CloudflareError({"success": False, "errors": [{"message": "Zone account id missing"}]})

        resolved = {"zone_id": zone_id, "account_id": account_id}
        self._zone_cache[zone] = resolved
        return resolved

    async def resolve_zone_for_hostname(self, hostname: str) -> dict[str, str]:
        hostname = hostname.strip().lower().strip(".")
        if not hostname or "." not in hostname:
            raise CloudflareError({"success": False, "errors": [{"message": f"Invalid hostname: {hostname}"}]})

        parts = hostname.split(".")
        # Try longest suffix first
        for i in range(len(parts) - 1):
            candidate = ".".join(parts[i:])
            try:
                info = await self._resolve_zone(candidate)
                return {"zone": candidate, **info}
            except CloudflareError:
                continue

        raise CloudflareError({"success": False, "errors": [{"message": f"Zone not found for: {hostname}"}]})
