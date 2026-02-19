from fastapi import APIRouter, Depends, HTTPException, Request

from .. import settings
from ..cloudflare.hostnames import validate_cf_service
from ..validation import validate_domain
from ..services import cloudflare as cf_service
from ..services.errors import ServiceError
from ..services import features as features_service


def _ensure_tunnel_enabled() -> None:
    if not features_service.is_tunnel_enabled():
        raise HTTPException(status_code=404, detail="Not found")


router = APIRouter(tags=["Cloudflare"], dependencies=[Depends(_ensure_tunnel_enabled)])


@router.get("/api/cf/hostnames")
def api_cf_hostnames():
    return cf_service.list_hostnames()


@router.post("/api/cf/hostnames")
async def api_cf_hostnames_create(request: Request):
    payload = await request.json()
    hostname = (payload.get("hostname") or "").strip().lower()
    if not hostname:
        raise HTTPException(status_code=400, detail="Hostname is required")

    if not validate_domain(hostname):
        raise HTTPException(status_code=400, detail=f"Invalid hostname: {hostname}")

    service = (payload.get("service") or "").strip() or settings.CLOUDFLARE_DEFAULT_SERVICE
    if not validate_cf_service(service):
        raise HTTPException(status_code=400, detail="Invalid service value")

    enabled = bool(payload.get("enabled", True))

    try:
        return await cf_service.create_or_update_hostname(hostname, service, enabled)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.patch("/api/cf/hostnames/{hostname}")
async def api_cf_hostnames_update(hostname: str, request: Request):
    payload = await request.json()
    hostname = hostname.strip().lower()

    if "service" in payload:
        service = (payload.get("service") or "").strip() or settings.CLOUDFLARE_DEFAULT_SERVICE
        if not validate_cf_service(service):
            raise HTTPException(status_code=400, detail="Invalid service value")
        payload["service"] = service

    try:
        return await cf_service.update_hostname(hostname, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.delete("/api/cf/hostnames/{hostname}")
async def api_cf_hostnames_delete(hostname: str):
    hostname = hostname.strip().lower()
    try:
        return await cf_service.delete_hostname(hostname)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/api/cf/apply")
async def api_cf_apply():
    try:
        return await cf_service.apply()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/api/cf/sync")
async def api_cf_sync():
    try:
        return await cf_service.sync_from_routes()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
