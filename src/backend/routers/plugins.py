from fastapi import APIRouter, Request, HTTPException

from ..services import plugins as plugins_service
from ..services.errors import ServiceError

router = APIRouter(tags=["Plugins"])


@router.get("/api/plugins")
def api_plugins():
    from ..storage import load_routes
    from ..plugins import default_plugins

    data = load_routes()
    return data.get("plugins", default_plugins())


@router.put("/api/plugins")
async def api_plugins_update(request: Request):
    payload = await request.json()
    try:
        return plugins_service.update_plugins(payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
