from fastapi import APIRouter, HTTPException, Request

from ..services import l4 as l4_service
from ..services.errors import ServiceError

router = APIRouter(tags=["L4"])


@router.get("/api/l4routes")
def api_l4routes():
    from ..storage import load_routes

    data = load_routes()
    return {"l4_routes": data.get("l4_routes", [])}


@router.put("/api/l4routes")
async def api_l4routes_update(request: Request):
    payload = await request.json()
    routes = payload.get("l4_routes") or []
    if not isinstance(routes, list):
        raise HTTPException(status_code=400, detail="l4_routes must be a list")
    try:
        return l4_service.update_l4_routes(routes)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
