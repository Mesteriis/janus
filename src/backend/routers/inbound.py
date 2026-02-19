import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from ..services import features as features_service
from ..services import inbound as inbound_service
from ..services.errors import ServiceError


def _ensure_tunnel_enabled() -> None:
    if not features_service.is_tunnel_enabled():
        raise HTTPException(status_code=404, detail="Not found")


def _ensure_vpn_enabled() -> None:
    if not features_service.is_vpn_enabled():
        raise HTTPException(status_code=404, detail="Not found")


cloudflare_router = APIRouter(tags=["Inbound"], dependencies=[Depends(_ensure_tunnel_enabled)])
vpn_router = APIRouter(tags=["Inbound"], dependencies=[Depends(_ensure_vpn_enabled)])


@cloudflare_router.get("/api/inbound/cloudflare")
async def api_inbound_cloudflare_status():
    try:
        return await inbound_service.get_cloudflare_status()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@cloudflare_router.put("/api/inbound/cloudflare/token")
async def api_inbound_cloudflare_token(request: Request):
    payload = await request.json()
    token = (payload or {}).get("token")
    try:
        return await inbound_service.set_cloudflare_token(str(token or ""))
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@cloudflare_router.delete("/api/inbound/cloudflare/token")
def api_inbound_cloudflare_token_delete():
    return inbound_service.clear_cloudflare_token()


@cloudflare_router.delete("/api/inbound/cloudflare/tunnels/{tunnel_id}")
async def api_inbound_cloudflare_tunnel_delete(tunnel_id: str, account_id: str = ""):
    try:
        return await inbound_service.delete_cloudflare_tunnel(tunnel_id=tunnel_id, account_id=account_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@cloudflare_router.post("/api/inbound/cloudflare/tunnels/{tunnel_id}/start")
async def api_inbound_cloudflare_tunnel_start(tunnel_id: str, account_id: str = ""):
    try:
        return await inbound_service.start_cloudflare_tunnel(tunnel_id=tunnel_id, account_id=account_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.get("/api/inbound/vpn")
def api_inbound_vpn_status():
    try:
        return inbound_service.get_vpn_status()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.post("/api/inbound/vpn/servers")
async def api_inbound_vpn_server_create(request: Request):
    payload = await request.json()
    name = str((payload or {}).get("name") or "")
    try:
        return await asyncio.to_thread(inbound_service.create_vpn_server, name)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.post("/api/inbound/vpn/servers/{server_id}/start")
def api_inbound_vpn_server_start(server_id: str):
    try:
        return inbound_service.start_vpn_server(server_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.post("/api/inbound/vpn/servers/{server_id}/stop")
def api_inbound_vpn_server_stop(server_id: str):
    try:
        return inbound_service.stop_vpn_server(server_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.delete("/api/inbound/vpn/servers/{server_id}")
def api_inbound_vpn_server_delete(server_id: str):
    try:
        return inbound_service.delete_vpn_server(server_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.post("/api/inbound/vpn/servers/{server_id}/clients")
async def api_inbound_vpn_client_create(server_id: str, request: Request):
    payload = await request.json()
    name = str((payload or {}).get("name") or "")
    try:
        return await asyncio.to_thread(inbound_service.add_vpn_client, server_id, name)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.get("/api/inbound/vpn/servers/{server_id}/clients/{client_id}/config")
def api_inbound_vpn_client_config(server_id: str, client_id: str):
    try:
        return inbound_service.get_vpn_client_config(server_id=server_id, client_id=client_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.post("/api/inbound/vpn/links")
async def api_inbound_vpn_link_create(request: Request):
    payload = await request.json()
    name = str((payload or {}).get("name") or "")
    config = str((payload or {}).get("config") or "")
    try:
        return await asyncio.to_thread(inbound_service.create_vpn_link, name, config)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.post("/api/inbound/vpn/links/{link_id}/start")
def api_inbound_vpn_link_start(link_id: str):
    try:
        return inbound_service.start_vpn_link(link_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.post("/api/inbound/vpn/links/{link_id}/stop")
def api_inbound_vpn_link_stop(link_id: str):
    try:
        return inbound_service.stop_vpn_link(link_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.delete("/api/inbound/vpn/links/{link_id}")
def api_inbound_vpn_link_delete(link_id: str):
    try:
        return inbound_service.delete_vpn_link(link_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@vpn_router.get("/api/inbound/vpn/links/{link_id}/config")
def api_inbound_vpn_link_config(link_id: str):
    try:
        return inbound_service.get_vpn_link_config(link_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
