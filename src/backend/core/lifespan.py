from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..services.lifespan import initialize_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_app()
    yield
