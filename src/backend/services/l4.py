from __future__ import annotations

from ..storage import load_routes, save_routes
from .provisioning import TRIGGER_L4, write_and_validate_config


def update_l4_routes(routes: list) -> dict:
    data = load_routes()
    data["l4_routes"] = routes
    save_routes(data)
    write_and_validate_config(data)
    return {"l4_routes": routes}
