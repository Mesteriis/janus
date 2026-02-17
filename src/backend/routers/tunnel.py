from fastapi import APIRouter, HTTPException, Request

from .. import settings
from ..services import tunnel as tunnel_service
from ..services.errors import ServiceError

router = APIRouter(tags=["Tunnel"])


@router.post("/api/cf/docker/start")
async def api_cf_docker_start(request: Request):
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    token = (payload.get("token") if isinstance(payload, dict) else None) or settings.CLOUDFLARE_TUNNEL_TOKEN
    if not token:
        raise HTTPException(status_code=400, detail="CLOUDFLARE_TUNNEL_TOKEN is empty")
    try:
        return tunnel_service.start(token)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/api/cf/docker/stop")
def api_cf_docker_stop():
    try:
        return tunnel_service.stop()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/cf/docker/status")
def api_cf_docker_status():
    try:
        return tunnel_service.status()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
