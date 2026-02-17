from .cloudflare import router as cloudflare_router
from .l4 import router as l4_router
from .auth import router as auth_router
from .plugins import router as plugins_router
from .raw import router as raw_router
from .routes import router as routes_router
from .tunnel import router as tunnel_router

routers = [
    auth_router,
    routes_router,
    raw_router,
    plugins_router,
    l4_router,
    cloudflare_router,
    tunnel_router,
]
