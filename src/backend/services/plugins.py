from __future__ import annotations

from ..plugins import default_plugins
from ..storage import load_routes, save_routes
from .provisioning import TRIGGER_PLUGINS, provision_after_routes_change


def get_plugins() -> dict:
    data = load_routes()
    return data.get("plugins", default_plugins())


async def update_plugins(payload: dict) -> dict:
    plugins = default_plugins()
    if isinstance(payload, dict):
        for key, val in payload.items():
            if key in plugins and isinstance(val, dict):
                plugins[key].update(val)
    data = load_routes()
    data["plugins"] = plugins
    save_routes(data)
    await provision_after_routes_change(data, TRIGGER_PLUGINS)
    return plugins
