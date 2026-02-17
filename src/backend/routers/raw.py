import json
import os
import subprocess
import tempfile

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .. import settings
from ..caddy import render_caddy_config, write_caddy_config
from ..storage import load_routes
from ..services import raw as raw_service
from ..services.errors import ServiceError

router = APIRouter(tags=["Config"])


@router.get("/api/raw/routes")
def api_raw_routes():
    data = load_routes()
    payload = {"routes": data.get("routes", [])}
    from io import StringIO

    buf = StringIO()
    json.dump(payload, buf, indent=2, ensure_ascii=False)
    buf.write("\n")
    return {"content": buf.getvalue()}


@router.put("/api/raw/routes")
async def api_raw_routes_update(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict) or "content" not in payload:
        raise HTTPException(status_code=400, detail="Content is required")
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc.msg}")
    if not isinstance(data, dict) or not isinstance(data.get("routes"), list):
        raise HTTPException(status_code=400, detail="JSON must contain routes array")

    try:
        return await raw_service.update_routes_raw(content, data)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/raw/config")
def api_raw_config():
    try:
        with open(settings.CADDY_CONFIG, "r", encoding="utf-8") as handle:
            return {"content": handle.read()}
    except FileNotFoundError:
        write_caddy_config(load_routes())
        with open(settings.CADDY_CONFIG, "r", encoding="utf-8") as handle:
            return {"content": handle.read()}


@router.post("/api/convert/caddyfile")
async def api_convert_caddyfile(request: Request):
    payload = await request.json()
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content is required")

    try:
        completed = subprocess.run(
            [settings.CADDY_BIN, "adapt", "--config", "/dev/stdin", "--adapter", "caddyfile", "--pretty"],
            input=content.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="caddy executable not found; set CADDY_BIN or install caddy")
    except subprocess.CalledProcessError as exc:
        error_text = (exc.stderr or b"").decode("utf-8").strip() or "caddy adapt error"
        raise HTTPException(status_code=400, detail=error_text)

    return {"json5": completed.stdout.decode("utf-8")}


@router.post("/api/raw/routes/validate")
async def api_raw_routes_validate(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict) or "content" not in payload:
        raise HTTPException(status_code=400, detail="Content is required")
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc.msg}")
    if not isinstance(data, dict) or not isinstance(data.get("routes"), list):
        raise HTTPException(status_code=400, detail="JSON must contain routes array")

    merged = load_routes()
    merged["routes"] = data.get("routes", [])
    config = render_caddy_config(merged)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json5", delete=False, encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = handle.name
        completed = subprocess.run(
            [settings.CADDY_BIN, "validate", "--config", temp_path, "--adapter", "json5"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        _ = completed.stdout
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="caddy executable not found; set CADDY_BIN or install caddy")
    except subprocess.CalledProcessError as exc:
        error_text = (exc.stderr or b"").decode("utf-8").strip() or "caddy validate error"
        raise HTTPException(status_code=400, detail=error_text)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    return {"status": "ok"}


@router.post("/api/validate/config")
def api_validate_config():
    try:
        completed = subprocess.run(
            [settings.CADDY_BIN, "validate", "--config", settings.CADDY_CONFIG, "--adapter", "json5"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="caddy executable not found; set CADDY_BIN or install caddy")
    except subprocess.CalledProcessError as exc:
        return PlainTextResponse((exc.stderr or b"").decode("utf-8"), status_code=400)
    return PlainTextResponse(completed.stdout.decode("utf-8") or "ok")
