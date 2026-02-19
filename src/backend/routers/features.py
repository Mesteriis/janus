from __future__ import annotations

from fastapi import APIRouter, Request

from ..services import features as features_service

router = APIRouter(tags=["Settings"])


@router.get("/api/settings/features")
def api_features():
    return features_service.get_features()


@router.put("/api/settings/features")
async def api_features_update(request: Request):
    payload = await request.json()
    return features_service.update_features(payload if isinstance(payload, dict) else {})


@router.get("/api/settings/runtime")
def api_settings_runtime():
    return features_service.get_runtime_settings()
