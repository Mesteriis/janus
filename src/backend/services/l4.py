from __future__ import annotations

from ..storage import load_routes, save_routes
from .provisioning import TRIGGER_L4, provision_after_routes_change


def get_l4_routes() -> dict:
    data = load_routes()
    return {"l4_routes": data.get("l4_routes", [])}


async def update_l4_routes(routes: list) -> dict:
    data = load_routes()
    data["l4_routes"] = routes
    save_routes(data)
    await provision_after_routes_change(data, TRIGGER_L4)
    return {"l4_routes": routes}
