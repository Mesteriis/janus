from __future__ import annotations

import copy
import uuid

from .errors import ServiceError
from .provisioning import (
    TRIGGER_CREATE,
    TRIGGER_DELETE,
    TRIGGER_PATCH,
    TRIGGER_REPLACE,
    provision_after_routes_change,
)
from ..storage import load_routes, save_routes


def _domains_conflict(domains: list[str], existing: dict, *, skip_id: str | None = None) -> bool:
    domains_set = set(domains)
    for route in existing.get("routes", []):
        if skip_id and route.get("id") == skip_id:
            continue
        if set(route.get("domains", [])) == domains_set:
            return True
    return False


def list_routes() -> dict:
    return load_routes()


async def create_route(validated: dict) -> dict:
    data = load_routes()
    if _domains_conflict(validated["domains"], data):
        raise ServiceError(409, "Route with same domains already exists")

    previous = copy.deepcopy(data)
    validated["id"] = str(uuid.uuid4())
    data.setdefault("routes", []).append(validated)
    save_routes(data)
    try:
        await provision_after_routes_change(data, TRIGGER_CREATE)
    except Exception:
        save_routes(previous)
        raise
    return validated


async def replace_route(route_id: str, validated: dict) -> dict:
    data = load_routes()
    if _domains_conflict(validated["domains"], data, skip_id=route_id):
        raise ServiceError(409, "Route with same domains already exists")

    for index, route in enumerate(data.get("routes", [])):
        if route.get("id") != route_id:
            continue
        previous = copy.deepcopy(data)
        validated["id"] = route_id
        data["routes"][index] = validated
        save_routes(data)
        try:
            await provision_after_routes_change(data, TRIGGER_REPLACE)
        except Exception:
            save_routes(previous)
            raise
        return validated

    raise ServiceError(404, "Route not found")


async def update_route(route_id: str, patch: dict) -> dict:
    data = load_routes()

    for route in data.get("routes", []):
        if route.get("id") != route_id:
            continue
        previous = copy.deepcopy(data)
        if "enabled" in patch:
            route["enabled"] = bool(patch["enabled"])
        if "domains" in patch:
            route["domains"] = patch["domains"]
        save_routes(data)
        try:
            await provision_after_routes_change(data, TRIGGER_PATCH)
        except Exception:
            save_routes(previous)
            raise
        return route

    raise ServiceError(404, "Route not found")


async def delete_route(route_id: str) -> dict:
    data = load_routes()
    previous = copy.deepcopy(data)
    routes = data.get("routes", [])
    updated = [route for route in routes if route.get("id") != route_id]
    if len(updated) == len(routes):
        raise ServiceError(404, "Route not found")
    data["routes"] = updated
    save_routes(data)
    try:
        await provision_after_routes_change(data, TRIGGER_DELETE)
    except Exception:
        save_routes(previous)
        raise
    return {"status": "deleted"}
