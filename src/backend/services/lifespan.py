from __future__ import annotations

import shutil
from pathlib import Path

from .. import settings
from ..storage import load_routes
from .provisioning import write_and_validate_config, sync_cloudflare_from_routes
from . import vpn as vpn_service
from . import caddy_runtime as caddy_runtime_service
from . import features as features_service


def _move_if_present(src: Path, dst: Path) -> None:
    if not src.exists() or src.resolve() == dst.resolve():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    shutil.move(str(src), str(dst))


def _migrate_data_layout() -> None:
    root = Path(settings.PROJECT_ROOT)

    # Cloudflare token file migrations.
    token_dst = Path(settings.CLOUDFLARE_API_TOKEN_FILE)
    token_sources = [
        root / "data" / "caddy" / "cloudflare_api_token.txt",
        root / "cloudflare_api_token.txt",
    ]
    for src in token_sources:
        _move_if_present(src, token_dst)

    # Cloudflare hostnames/state migrations.
    hostnames_dst = Path(settings.CLOUDFLARE_HOSTNAMES_FILE)
    state_dst = Path(settings.CF_STATE_FILE)
    hostnames_sources = [
        root / "cloudflared" / "hostnames.json",
        root / "legacy" / "cloudflared" / "hostnames.json",
    ]
    state_sources = [
        root / "cloudflared" / "state.json",
        root / "legacy" / "cloudflared" / "state.json",
    ]
    for src in hostnames_sources:
        _move_if_present(src, hostnames_dst)
    for src in state_sources:
        _move_if_present(src, state_dst)


def initialize_app() -> None:
    features_service.ensure_runtime_settings_file()
    _migrate_data_layout()
    data = load_routes()
    write_and_validate_config(data)
    vpn_service.reconcile_on_startup()
    caddy_runtime_service.reconcile_on_startup()


async def sync_cloudflare_on_startup() -> None:
    try:
        data = load_routes()
        sync_cloudflare_from_routes(data)
    except Exception:  # noqa: BLE001
        # Startup must not fail on Cloudflare transient errors.
        return None
