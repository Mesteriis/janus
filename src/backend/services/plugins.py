from __future__ import annotations

from ..plugins import default_plugins
from ..storage import load_routes, save_routes
from .provisioning import TRIGGER_PLUGINS, write_and_validate_config


def update_plugins(payload: dict) -> dict:
    plugins = default_plugins()
    if isinstance(payload, dict):
        for key, val in payload.items():
            if key in plugins and isinstance(val, dict):
                plugins[key].update(val)
    data = load_routes()
    data["plugins"] = plugins
    save_routes(data)
    write_and_validate_config(data)
    return plugins
