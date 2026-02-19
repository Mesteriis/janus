from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..services import caddy_runtime as runtime_service
from ..services.errors import ServiceError

router = APIRouter(tags=["Caddy Runtime"])


@router.get("/api/caddy/runtime/status")
def api_caddy_runtime_status(include_logs: bool = True):
    try:
        return runtime_service.get_status(include_logs=include_logs)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/caddy/runtime/logs")
def api_caddy_runtime_logs(source: str = "all", limit: int = 200, since_id: int = 0):
    try:
        return runtime_service.get_logs(source=source, limit=limit, since_id=since_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/api/caddy/runtime/install")
async def api_caddy_runtime_install(request: Request):
    payload = await request.json()
    addons = list((payload or {}).get("addons") or [])
    reinstall = bool((payload or {}).get("reinstall", False))
    try:
        return runtime_service.start_install(addons=addons, reinstall=reinstall)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/api/caddy/runtime/start")
def api_caddy_runtime_start():
    try:
        return runtime_service.start_container()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/api/caddy/runtime/stop")
def api_caddy_runtime_stop():
    try:
        return runtime_service.stop_container()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/api/caddy/runtime/rollback")
async def api_caddy_runtime_rollback(request: Request):
    payload = await request.json()
    build_id = str((payload or {}).get("build_id") or "")
    try:
        return runtime_service.rollback(target_build_id=build_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/caddy/runtime/stream")
def api_caddy_runtime_stream(source: str = "all"):
    clean_source = str(source or "all").strip().lower()

    def _event_stream():
        since_id = 0
        while True:
            try:
                payload = runtime_service.stream_payload(source=clean_source, since_id=since_id)
                since_id = int(payload.get("next_since_id") or since_id)
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except Exception as exc:  # noqa: BLE001
                message = {"error": str(exc)}
                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
            time.sleep(2)

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
