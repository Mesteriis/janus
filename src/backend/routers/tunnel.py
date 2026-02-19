from fastapi import APIRouter, Depends, HTTPException, Request

from ..services import features as features_service
from ..services import tunnel as tunnel_service
from ..services.errors import ServiceError


def _ensure_tunnel_enabled() -> None:
    if not features_service.is_tunnel_enabled():
        raise HTTPException(status_code=404, detail="Not found")


router = APIRouter(tags=["Tunnel"], dependencies=[Depends(_ensure_tunnel_enabled)])


@router.post("/api/cf/docker/start")
async def api_cf_docker_start(request: Request):
    payload = await request.json() if request else {}
    token = str((payload or {}).get("token") or "").strip()
    try:
        return tunnel_service.start(token or None)
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
