from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from ..services.lifespan import initialize_app, sync_cloudflare_on_startup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_app()
    await sync_cloudflare_on_startup()
    yield
