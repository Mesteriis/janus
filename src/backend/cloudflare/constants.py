from dataclasses import dataclass
from typing import Literal

PermissionType = Literal["read", "edit"]
TOKEN_NAME="PVE Tunnel Controller"
PERMISSIONS=[
    {"key": "argotunnel", "type": "edit"},  # Cloudflare Tunnel
    {"key": "dns", "type": "edit"},          # DNS
    {"key": "zone", "type": "read"},         # Zone read (часто нужен)
]


@dataclass(frozen=True)
class DnsException:
    fqdn: str
    record_type: str = "A"   # A | AAAA | CNAME
    content: str = ""
