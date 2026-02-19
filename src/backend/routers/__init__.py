from .cloudflare import router as cloudflare_router
from .auth import router as auth_router
from .caddy_runtime import router as caddy_runtime_router
from .features import router as features_router
from .inbound import cloudflare_router as inbound_cloudflare_router
from .inbound import vpn_router as inbound_vpn_router
from .l4 import router as l4_router
from .plugins import router as plugins_router
from .raw import router as raw_router
from .routes import router as routes_router
from .tunnel import router as tunnel_router

routers = [
    auth_router,
    features_router,
    routes_router,
    raw_router,
    plugins_router,
    l4_router,
    caddy_runtime_router,
    inbound_cloudflare_router,
    inbound_vpn_router,
    cloudflare_router,
    tunnel_router,
]
