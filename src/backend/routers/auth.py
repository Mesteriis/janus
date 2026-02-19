from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .. import settings
from ..auth import (
    auth_enabled,
    check_password,
    clear_sessions,
    is_session_token_valid,
    issue_session_token,
    revoke_session_token,
    set_password,
)

router = APIRouter(tags=["Auth"])


@router.get("/api/auth/status")
def auth_status(request: Request):
    enabled = auth_enabled()
    if not enabled:
        return {"enabled": False, "authorized": True}
    token = request.cookies.get(settings.AUTH_COOKIE_NAME) or request.headers.get("X-Auth-Token")
    return {"enabled": True, "authorized": is_session_token_valid(token)}


@router.post("/api/auth/login")
async def auth_login(request: Request):
    payload = await request.json()
    password = payload.get("password") if isinstance(payload, dict) else None
    if not auth_enabled():
        return {"enabled": False, "authorized": True}
    if not isinstance(password, str) or not password.strip():
        raise HTTPException(status_code=400, detail="Password is required")
    if not check_password(password.strip()):
        raise HTTPException(status_code=401, detail="Invalid password")
    session_token = issue_session_token()
    response = JSONResponse({"status": "ok"})
    response.set_cookie(settings.AUTH_COOKIE_NAME, session_token, httponly=True, samesite="lax")
    return response


@router.post("/api/auth/logout")
def auth_logout(request: Request):
    token = request.cookies.get(settings.AUTH_COOKIE_NAME) or request.headers.get("X-Auth-Token")
    revoke_session_token(token)
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(settings.AUTH_COOKIE_NAME)
    return response


@router.put("/api/auth/config")
async def auth_config(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict) or "enabled" not in payload:
        raise HTTPException(status_code=400, detail="enabled is required")
    enabled = payload.get("enabled")

    if enabled is True:
        password = payload.get("password")
        if not isinstance(password, str) or not password.strip():
            raise HTTPException(status_code=400, detail="Password is required")
        set_password(password.strip())
        session_token = issue_session_token()
        response = JSONResponse({"enabled": True, "authorized": True})
        response.set_cookie(settings.AUTH_COOKIE_NAME, session_token, httponly=True, samesite="lax")
        return response

    if enabled is False:
        if auth_enabled():
            session_token = request.cookies.get(settings.AUTH_COOKIE_NAME) or request.headers.get("X-Auth-Token")
            password = str(payload.get("password") or "")
            if not is_session_token_valid(session_token) and not check_password(password):
                raise HTTPException(status_code=401, detail="Invalid password")
        set_password("")
        clear_sessions()
        response = JSONResponse({"enabled": False, "authorized": True})
        response.delete_cookie(settings.AUTH_COOKIE_NAME)
        return response

    raise HTTPException(status_code=400, detail="enabled must be true or false")
