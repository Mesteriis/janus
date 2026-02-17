from fastapi import APIRouter

from .routers import routers

router = APIRouter()
for r in routers:
    router.include_router(r)
