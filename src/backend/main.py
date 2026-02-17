from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import router
from .core import configure_logging, lifespan
from .core.middleware import AuthMiddleware, CorrelationIdMiddleware
from . import settings


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR), check_dir=False), name="static")

    @app.get("/")
    def index():
        index_path = settings.STATIC_DIR / "index.html"
        if not index_path.exists():
            from fastapi.responses import PlainTextResponse

            return PlainTextResponse("Frontend not built. Run the Vite build.", status_code=503)
        from fastapi.responses import FileResponse

        return FileResponse(str(index_path))

    return app


app = create_app()
