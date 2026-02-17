import json
from typing import Dict

from . import settings
from .plugins import default_plugins
from .utils import ensure_parent


def load_routes() -> Dict:
    try:
        with open(settings.ROUTES_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        data = {}
    if "routes" not in data:
        data["routes"] = []
    if "plugins" not in data:
        data["plugins"] = default_plugins()
    if "l4_routes" not in data:
        data["l4_routes"] = []
    return data


def save_routes(data: Dict) -> None:
    ensure_parent(settings.ROUTES_FILE)
    with open(settings.ROUTES_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def save_routes_raw(content: str) -> Dict:
    ensure_parent(settings.ROUTES_FILE)
    with open(settings.ROUTES_FILE, "w", encoding="utf-8") as handle:
        handle.write(content.rstrip() + "\n")
    with open(settings.ROUTES_FILE, "r", encoding="utf-8") as handle:
        return json.load(handle)
