from fastapi import APIRouter, HTTPException, Request

from ..validation import normalize_domains, parse_headers, parse_header_values, validate_route_payload
from ..services import routes as routes_service
from ..services.errors import ServiceError

router = APIRouter(tags=["Routes"])


def _handle_service_error(exc: ServiceError):
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/routes")
def api_routes():
    return routes_service.list_routes()


@router.post("/api/routes")
async def api_routes_create(request: Request):
    payload = await request.json()
    try:
        payload["headers_up"] = parse_headers(payload.get("headers_up", []))
        payload["headers_down"] = parse_headers(payload.get("headers_down", []))
        payload["response_headers"] = parse_headers(payload.get("response_headers", []))
        payload["match_headers"] = parse_header_values(payload.get("match_headers", []))
        for pr in payload.get("path_routes") or []:
            pr["match_headers"] = parse_header_values(pr.get("match_headers", []))
        validated = validate_route_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        return await routes_service.create_route(validated)
    except ServiceError as exc:
        _handle_service_error(exc)


@router.patch("/api/routes/{route_id}")
async def api_routes_update(route_id: str, request: Request):
    payload = await request.json()
    if "domains" in payload:
        payload["domains"] = normalize_domains(payload["domains"])
    try:
        return await routes_service.update_route(route_id, payload)
    except ServiceError as exc:
        _handle_service_error(exc)


@router.put("/api/routes/{route_id}")
async def api_routes_replace(route_id: str, request: Request):
    payload = await request.json()
    try:
        payload["headers_up"] = parse_headers(payload.get("headers_up", []))
        payload["headers_down"] = parse_headers(payload.get("headers_down", []))
        payload["response_headers"] = parse_headers(payload.get("response_headers", []))
        payload["match_headers"] = parse_header_values(payload.get("match_headers", []))
        for pr in payload.get("path_routes") or []:
            pr["match_headers"] = parse_header_values(pr.get("match_headers", []))
        validated = validate_route_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        return await routes_service.replace_route(route_id, validated)
    except ServiceError as exc:
        _handle_service_error(exc)


@router.delete("/api/routes/{route_id}")
async def api_routes_delete(route_id: str):
    try:
        return await routes_service.delete_route(route_id)
    except ServiceError as exc:
        _handle_service_error(exc)
