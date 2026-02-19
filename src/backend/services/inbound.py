from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from .. import settings
from ..cloudflare.checker import CloudflareTokenCheckerSDK
from ..cloudflare.client import CloudFlare
from ..cloudflare.sdk import AsyncCloudflare
from ..cloudflare.store import TunnelStateStorage
from ..docker_ctl import start_tunnel, stop_tunnel_container
from . import vpn as vpn_service
from .errors import ServiceError


def _token_path() -> Path:
    return Path(settings.CLOUDFLARE_API_TOKEN_FILE)


def _safe_tunnel_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip().lower())


def _full_container_name(tunnel_id: str) -> str:
    return f"{settings.CF_TUNNEL_CONTAINER}-{_safe_tunnel_id(tunnel_id)}"


def _read_token_file() -> str:
    path = _token_path()
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _write_token_file(token: str) -> None:
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token.strip() + "\n", encoding="utf-8")


def _clear_token_file() -> None:
    path = _token_path()
    if path.exists():
        path.unlink()


def _token_url() -> str:
    return CloudFlare.gen_token_url()


def _effective_token() -> tuple[str, str]:
    from_file = _read_token_file()
    if from_file:
        return from_file, "file"
    from_env = (settings.CLOUDFLARE_API_TOKEN or "").strip()
    if from_env:
        return from_env, "env"
    return "", "none"


async def _cf_get(client: AsyncCloudflare, token: str, path: str, *, params: dict[str, Any] | None = None) -> dict:
    response = await client._client.get(
        path,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params=params,
    )
    data = response.json()
    if not isinstance(data, dict):
        raise ServiceError(502, "Cloudflare returned invalid response")
    if not data.get("success", False):
        errors = data.get("errors") or []
        message = (errors[0].get("message") if errors and isinstance(errors[0], dict) else None) or "Cloudflare API error"
        raise ServiceError(502, message)
    return data


async def _cf_delete(client: AsyncCloudflare, token: str, path: str) -> dict:
    response = await client._client.delete(
        path,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    data = response.json()
    if not isinstance(data, dict):
        raise ServiceError(502, "Cloudflare returned invalid response")
    if not data.get("success", False):
        errors = data.get("errors") or []
        message = (errors[0].get("message") if errors and isinstance(errors[0], dict) else None) or "Cloudflare API error"
        raise ServiceError(502, message)
    return data


async def _cf_put(client: AsyncCloudflare, token: str, path: str, payload: dict[str, Any]) -> dict:
    response = await client._client.put(
        path,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
    )
    data = response.json()
    if not isinstance(data, dict):
        raise ServiceError(502, "Cloudflare returned invalid response")
    if not data.get("success", False):
        errors = data.get("errors") or []
        message = (errors[0].get("message") if errors and isinstance(errors[0], dict) else None) or "Cloudflare API error"
        raise ServiceError(502, message)
    return data


async def _cf_get_paged(client: AsyncCloudflare, token: str, path: str, *, params: dict[str, Any] | None = None) -> list[dict]:
    page = 1
    per_page = 100
    result: list[dict] = []
    while True:
        payload = dict(params or {})
        payload.update({"page": page, "per_page": per_page})
        data = await _cf_get(client, token, path, params=payload)
        batch = data.get("result") or []
        if isinstance(batch, list):
            result.extend([item for item in batch if isinstance(item, dict)])
        info = data.get("result_info") or {}
        total_pages = int(info.get("total_pages") or 1)
        if page >= total_pages:
            break
        page += 1
    return result


async def _accessible_accounts(client: AsyncCloudflare, token: str) -> list[dict]:
    try:
        accounts = await _cf_get_paged(client, token, "/accounts")
    except Exception:
        accounts = []
    if accounts:
        return accounts

    fallback: dict[str, dict] = {}
    try:
        zones = await _cf_get_paged(client, token, "/zones")
    except Exception:
        zones = []
    for zone in zones:
        account = zone.get("account")
        if not isinstance(account, dict):
            continue
        account_id = str(account.get("id") or "").strip()
        if not account_id:
            continue
        fallback[account_id] = {
            "id": account_id,
            "name": str(account.get("name") or account_id),
        }

    if fallback:
        return list(fallback.values())

    try:
        memberships = await _cf_get_paged(client, token, "/memberships")
    except Exception:
        memberships = []
    for membership in memberships:
        account = membership.get("account")
        if not isinstance(account, dict):
            continue
        account_id = str(account.get("id") or "").strip()
        if not account_id:
            continue
        fallback[account_id] = {
            "id": account_id,
            "name": str(account.get("name") or account_id),
        }

    return list(fallback.values())


def _extract_ingress_domains(config_data: dict) -> set[str]:
    domains: set[str] = set()
    ingress = ((config_data.get("result") or {}).get("config") or {}).get("ingress") or []
    if not isinstance(ingress, list):
        return domains
    for rule in ingress:
        if not isinstance(rule, dict):
            continue
        hostname = str(rule.get("hostname") or "").strip().lower()
        if hostname:
            domains.add(hostname)
    return domains


async def _fetch_tunnels_and_domains(token: str) -> list[dict]:
    sdk = AsyncCloudflare(api_token=token)

    accounts = await _accessible_accounts(sdk, token)
    tunnels: dict[str, dict] = {}
    tunnel_domains: dict[str, set[str]] = {}

    for account in accounts:
        account_id = str(account.get("id") or "").strip()
        if not account_id:
            continue
        account_name = str(account.get("name") or account_id)

        for tunnel in await _cf_get_paged(sdk, token, f"/accounts/{account_id}/cfd_tunnel"):
            tunnel_id = str(tunnel.get("id") or "").strip()
            if not tunnel_id:
                continue
            tunnels[tunnel_id] = {
                "id": tunnel_id,
                "name": tunnel.get("name") or tunnel_id,
                "status": tunnel.get("status") or "unknown",
                "account_id": account_id,
                "account_name": account_name,
                "created_at": tunnel.get("created_at"),
                "container_name": _full_container_name(tunnel_id),
            }
            tunnel_domains.setdefault(tunnel_id, set())
            try:
                cfg_data = await _cf_get(sdk, token, f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations")
                tunnel_domains[tunnel_id].update(_extract_ingress_domains(cfg_data))
            except Exception:
                # Ingress config can be absent for newly created tunnel.
                pass

        zones = await _cf_get_paged(sdk, token, "/zones", params={"account.id": account_id})
        if not zones:
            zones = [z for z in await _cf_get_paged(sdk, token, "/zones") if str(((z.get("account") or {}).get("id") or "")).strip() == account_id]
        for zone in zones:
            zone_id = str(zone.get("id") or "").strip()
            if not zone_id:
                continue
            records = await _cf_get_paged(sdk, token, f"/zones/{zone_id}/dns_records", params={"type": "CNAME"})
            for record in records:
                content = str(record.get("content") or "").strip().lower()
                if not content.endswith(".cfargotunnel.com"):
                    continue
                tunnel_id = content.split(".", 1)[0]
                if tunnel_id not in tunnel_domains:
                    continue
                hostname = str(record.get("name") or "").strip().lower()
                if hostname:
                    tunnel_domains[tunnel_id].add(hostname)

    result: list[dict] = []
    for tunnel_id, tunnel in tunnels.items():
        item = dict(tunnel)
        item["domains"] = sorted(tunnel_domains.get(tunnel_id, set()))
        result.append(item)

    result.sort(key=lambda item: (str(item.get("name") or "").lower(), str(item.get("id") or "")))
    return result


async def _find_tunnel_account(client: AsyncCloudflare, token: str, tunnel_id: str) -> str:
    accounts = await _accessible_accounts(client, token)
    for account in accounts:
        account_id = str(account.get("id") or "").strip()
        if not account_id:
            continue
        try:
            await _cf_get(client, token, f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}")
            return account_id
        except Exception:
            continue
    return ""


async def _get_tunnel_token(client: AsyncCloudflare, token: str, account_id: str, tunnel_id: str) -> str:
    data = await _cf_get(client, token, f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token")
    result = data.get("result")
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        maybe = str(result.get("token") or "").strip()
        if maybe:
            return maybe
    return ""


async def _route_tunnel_to_caddy(client: AsyncCloudflare, token: str, account_id: str, tunnel_id: str) -> None:
    service = (settings.CLOUDFLARE_DEFAULT_SERVICE or "").strip() or "http://127.0.0.1:80"
    payload = {
        "config": {
            "ingress": [
                {"service": service},
            ]
        }
    }
    await _cf_put(client, token, f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations", payload)


async def get_cloudflare_status() -> dict:
    token, source = _effective_token()
    has_token = bool(token)
    payload = {
        "token_present": has_token,
        "token_source": source,
        "token_file": str(_token_path()),
        "token_generation_url": _token_url(),
        "tunnels": [],
        "vpn": {"status": "not_configured"},
    }
    if not has_token:
        return payload

    try:
        check = await CloudflareTokenCheckerSDK(token).check()
        if not check.token_active:
            raise ServiceError(400, "Stored Cloudflare token is invalid")
        payload["tunnels"] = await _fetch_tunnels_and_domains(token)
        return payload
    except ServiceError:
        raise
    except Exception as exc:
        raise ServiceError(502, f"Failed to fetch Cloudflare tunnels: {exc}")


async def set_cloudflare_token(token: str) -> dict:
    clean = (token or "").strip()
    if not clean:
        raise ServiceError(400, "Token is required")

    check = await CloudflareTokenCheckerSDK(clean).check()
    if not check.token_active:
        raise ServiceError(400, "Invalid Cloudflare token")

    _write_token_file(clean)

    # Keep state file in sync for existing flows.
    TunnelStateStorage(Path(settings.CF_STATE_FILE)).set_api_token(clean)

    return await get_cloudflare_status()


async def delete_cloudflare_tunnel(tunnel_id: str, account_id: str = "") -> dict:
    clean_tunnel = (tunnel_id or "").strip()
    if not clean_tunnel:
        raise ServiceError(400, "Tunnel ID is required")

    token, _ = _effective_token()
    removed_remote = {"status": "skipped", "reason": "token_missing"}
    resolved_account_id = (account_id or "").strip()
    if token:
        sdk = AsyncCloudflare(api_token=token)
        if not resolved_account_id:
            resolved_account_id = await _find_tunnel_account(sdk, token, clean_tunnel)
        if resolved_account_id:
            await _cf_delete(sdk, token, f"/accounts/{resolved_account_id}/cfd_tunnel/{clean_tunnel}")
            removed_remote = {"status": "deleted", "tunnel_id": clean_tunnel, "account_id": resolved_account_id}
        else:
            removed_remote = {"status": "skipped", "reason": "tunnel_not_found"}

    removed = [await asyncio.to_thread(stop_tunnel_container, _full_container_name(clean_tunnel))]
    status = await get_cloudflare_status()
    status["docker"] = {"removed": removed}
    status["cloudflare"] = removed_remote
    return status


async def start_cloudflare_tunnel(tunnel_id: str, account_id: str = "") -> dict:
    token, _ = _effective_token()
    if not token:
        raise ServiceError(400, "Cloudflare token is not configured")
    clean_tunnel = (tunnel_id or "").strip()
    if not clean_tunnel:
        raise ServiceError(400, "Tunnel ID is required")

    sdk = AsyncCloudflare(api_token=token)
    resolved_account_id = (account_id or "").strip()
    if not resolved_account_id:
        resolved_account_id = await _find_tunnel_account(sdk, token, clean_tunnel)
    if not resolved_account_id:
        raise ServiceError(404, "Tunnel not found")

    tunnel_token = await _get_tunnel_token(sdk, token, resolved_account_id, clean_tunnel)
    if not tunnel_token:
        raise ServiceError(502, "Failed to fetch tunnel token")

    await _route_tunnel_to_caddy(sdk, token, resolved_account_id, clean_tunnel)
    full_name = _full_container_name(clean_tunnel)
    try:
        started = await asyncio.to_thread(start_tunnel, tunnel_token, full_name)
    except Exception as exc:
        raise ServiceError(500, f"Failed to start tunnel container: {exc}")

    status = await get_cloudflare_status()
    return {
        "started": True,
        "tunnel_id": clean_tunnel,
        "account_id": resolved_account_id,
        "docker": started,
        "status": status,
    }


def clear_cloudflare_token() -> dict:
    _clear_token_file()
    TunnelStateStorage(Path(settings.CF_STATE_FILE)).set_api_token("")
    return {
        "status": "cleared",
        "token_present": False,
        "token_source": "none",
        "token_file": str(_token_path()),
        "token_generation_url": _token_url(),
    }


def get_vpn_status() -> dict:
    return vpn_service.get_status()


def create_vpn_server(name: str = "") -> dict:
    return vpn_service.create_server(name=name)


def start_vpn_server(server_id: str) -> dict:
    return vpn_service.start_server(server_id)


def stop_vpn_server(server_id: str) -> dict:
    return vpn_service.stop_server(server_id)


def delete_vpn_server(server_id: str) -> dict:
    return vpn_service.delete_server(server_id)


def add_vpn_client(server_id: str, name: str = "") -> dict:
    return vpn_service.add_client(server_id=server_id, name=name)


def get_vpn_client_config(server_id: str, client_id: str) -> dict:
    return vpn_service.get_client_config(server_id=server_id, client_id=client_id)


def create_vpn_link(name: str = "", config: str = "") -> dict:
    return vpn_service.create_link(name=name, config=config)


def start_vpn_link(link_id: str) -> dict:
    return vpn_service.start_link(link_id)


def stop_vpn_link(link_id: str) -> dict:
    return vpn_service.stop_link(link_id)


def delete_vpn_link(link_id: str) -> dict:
    return vpn_service.delete_link(link_id)


def get_vpn_link_config(link_id: str) -> dict:
    return vpn_service.get_link_config(link_id)
