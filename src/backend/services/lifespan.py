from __future__ import annotations

import logging

from ..caddy import write_caddy_config
from ..storage import load_routes
from ..cloudflare.flow import sync_cloudflare_from_routes
from .provisioning import write_and_validate_config

logger = logging.getLogger(__name__)


def initialize_app() -> None:
    data = load_routes()
    write_and_validate_config(data)


async def sync_cloudflare_on_startup() -> None:
    try:
        await sync_cloudflare_from_routes()
    except Exception:
        logger.exception("Cloudflare sync failed")
