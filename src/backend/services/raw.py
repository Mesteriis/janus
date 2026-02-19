from __future__ import annotations

import json

from .. import settings
from ..caddyfile import write_default_caddyfile
from .provisioning import TRIGGER_RAW, provision_after_routes_change
from .errors import ServiceError
from ..storage import load_routes, save_routes


def parse_routes_content(content: str) -> dict:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ServiceError(400, f"Invalid JSON: {exc.msg}")
    if not isinstance(parsed, dict) or not isinstance(parsed.get("routes"), list):
        raise ServiceError(400, "JSON must contain routes array")
    return parsed


def get_routes_raw() -> dict:
    data = load_routes()
    payload = {"routes": data.get("routes", [])}
    return {"content": json.dumps(payload, ensure_ascii=False, indent=2) + "\n"}


def _read_caddyfile_or_create_default() -> str:
    try:
        return settings.CADDYFILE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        write_default_caddyfile(load_routes())
        return settings.CADDYFILE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise ServiceError(500, str(exc))


def get_raw_config() -> dict:
    return {"content": _read_caddyfile_or_create_default()}


def get_caddyfile() -> dict:
    return {"content": _read_caddyfile_or_create_default(), "path": str(settings.CADDYFILE_PATH)}


async def update_routes_raw(content: str) -> dict:
    parsed = parse_routes_content(content)
    current = load_routes()
    current["routes"] = parsed.get("routes", [])
    save_routes(current)
    await provision_after_routes_change(current, TRIGGER_RAW)
    return {"status": "saved"}


def save_caddyfile(content: str) -> dict:
    clean_content = content.rstrip() + "\n"
    try:
        settings.CADDYFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings.CADDYFILE_PATH.write_text(clean_content, encoding="utf-8")
    except OSError as exc:
        raise ServiceError(500, str(exc))
    return {"status": "saved", "path": str(settings.CADDYFILE_PATH)}


def caddyfile_exists() -> bool:
    return settings.CADDYFILE_PATH.exists()


def write_default_config() -> dict:
    path = write_default_caddyfile(load_routes())
    return {"status": "saved", "path": path}
