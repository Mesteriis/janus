from __future__ import annotations

from .provisioning import TRIGGER_RAW, provision_after_routes_change
from ..storage import load_routes, save_routes


async def update_routes_raw(content: str, data: dict) -> dict:
    current = load_routes()
    current["routes"] = data.get("routes", [])
    save_routes(current)
    await provision_after_routes_change(current, TRIGGER_RAW)
    return {"status": "saved"}
