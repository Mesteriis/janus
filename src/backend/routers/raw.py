from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from ..services import raw as raw_service
from ..services.errors import ServiceError

router = APIRouter(tags=["Config"])


@router.get("/api/raw/routes")
def api_raw_routes():
    return raw_service.get_routes_raw()


@router.put("/api/raw/routes")
async def api_raw_routes_update(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict) or "content" not in payload:
        raise HTTPException(status_code=400, detail="Content is required")
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    try:
        return await raw_service.update_routes_raw(content)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/raw/config")
def api_raw_config():
    try:
        return raw_service.get_raw_config()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/api/convert/caddyfile")
async def api_convert_caddyfile(_request: Request):
    raise HTTPException(status_code=501, detail="Caddy adapt is isolated in this mode")


@router.post("/api/raw/routes/validate")
async def api_raw_routes_validate(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict) or "content" not in payload:
        raise HTTPException(status_code=400, detail="Content is required")
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    try:
        raw_service.parse_routes_content(content)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return {"status": "ok"}


@router.post("/api/validate/config")
def api_validate_config():
    if not raw_service.caddyfile_exists():
        return PlainTextResponse("Caddyfile not found", status_code=404)
    return PlainTextResponse("ok")


@router.get("/api/caddyfile")
def api_get_caddyfile():
    try:
        return raw_service.get_caddyfile()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.put("/api/caddyfile")
async def api_put_caddyfile(request: Request):
    payload = await request.json()
    content = (payload or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    try:
        return raw_service.save_caddyfile(content)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/api/caddyfile/default")
def api_default_caddyfile():
    try:
        return raw_service.write_default_config()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
