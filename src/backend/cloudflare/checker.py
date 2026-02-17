from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import warnings

warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
    category=UserWarning,
)
from .sdk import AsyncCloudflare


@dataclass
class TokenCheckResult:
    ok: bool
    token_active: bool
    can_list_zones: bool
    can_edit_dns: bool
    can_tunnel_rw: bool
    chosen_zone_id: Optional[str]
    chosen_account_id: Optional[str]
    details: dict[str, Any]


class CloudflareTokenCheckerSDK:
    """
    Проверка Cloudflare API Token:
    - verify token (без побочных эффектов)

    Без выбора зон и без DNS/Tunnel canary.
    """

    def __init__(self, token: str) -> None:
        self.token = token
        self.client = AsyncCloudflare(api_token=token)

        # ЯВНО задаём headers для raw-вызовов
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ---------- VERIFY TOKEN ----------

    async def verify_token(self) -> tuple[bool, dict]:
        """
        GET /user/tokens/verify
        """
        try:
            r = await self.client._client.get(
                "/user/tokens/verify",
                headers=self._headers,
            )
            data = r.json()
            return bool(data.get("success")), data
        except Exception as e:
            return False, {"success": False, "errors": [{"message": str(e)}], "result": None}

    # ---------- ZONE + ACCOUNT ----------

    async def pick_zone_and_account(self) -> tuple[Optional[str], Optional[str], bool, dict]:
        """
        Берём первую доступную зону и account_id из неё
        """
        try:
            page = await self.client.zones.list(per_page=1, page=1)
            if not page.result:
                return None, None, False, {"success": True, "result": []}

            z = page.result[0]
            zone_id = z.id
            account_id = getattr(z.account, "id", None) if z.account else None

            if not account_id:
                return zone_id, None, False, {"error": "zone.account.id missing", "zone": z.to_dict()}

            return zone_id, account_id, True, {"zone": z.to_dict()}

        except Exception as e:
            return None, None, False, {"success": False, "errors": [{"message": str(e)}]}

    # ---------- DNS EDIT CHECK ----------

    async def dns_canary(self, zone_id: str) -> tuple[bool, dict]:
        """
        Create TXT -> Delete TXT
        """
        try:
            rec = await self.client.dns.records.create(
                zone_id=zone_id,
                type="TXT",
                name="_cf_token_probe",
                content="probe",
                ttl=120,
            )
            await self.client.dns.records.delete(
                zone_id=zone_id,
                dns_record_id=rec.id,
            )
            return True, {"created_id": rec.id}

        except Exception as e:
            return False, {"success": False, "error": str(e)}

    # ---------- TUNNEL EDIT CHECK ----------

    async def tunnel_canary(self, account_id: str) -> tuple[bool, dict]:
        """
        POST /accounts/{account_id}/cfd_tunnel
        DELETE /accounts/{account_id}/cfd_tunnel/{tunnel_id}
        """
        try:
            create_r = await self.client._client.post(
                f"/accounts/{account_id}/cfd_tunnel",
                headers=self._headers,
                json={"name": "token-probe", "config_src": "cloudflare"},
            )
            create_data = create_r.json()
            if not create_data.get("success"):
                return False, {"create": create_data}

            tunnel_id = create_data["result"]["id"]

            delete_r = await self.client._client.delete(
                f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}",
                headers=self._headers,
            )
            delete_data = delete_r.json()

            return True, {"create": create_data, "delete": delete_data}

        except Exception as e:
            return False, {"success": False, "error": str(e)}

    # ---------- FULL CHECK ----------

    async def check(self) -> TokenCheckResult:
        details: dict[str, Any] = {}

        token_active, verify_payload = await self.verify_token()
        details["verify"] = verify_payload
        # NOTE: token checker only validates token status.
        # No DNS/tunnel canaries to avoid side-effects.
        zone_id = None
        account_id = None
        can_list = False
        can_dns = False
        can_tunnel = False
        ok = token_active

        return TokenCheckResult(
            ok=ok,
            token_active=token_active,
            can_list_zones=can_list,
            can_edit_dns=can_dns,
            can_tunnel_rw=can_tunnel,
            chosen_zone_id=zone_id,
            chosen_account_id=account_id,
            details=details,
        )
