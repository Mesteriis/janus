import docker
from docker.errors import NotFound, APIError

from . import settings


def _client():
    return docker.from_env()


def tunnel_command(token: str) -> list[str]:
    return ["tunnel", "--no-autoupdate", "run", "--token", token]


def start_tunnel(token: str | None = None) -> dict:
    token = token or settings.CLOUDFLARE_TUNNEL_TOKEN
    if not token:
        raise ValueError("CLOUDFLARE_TUNNEL_TOKEN is empty")
    client = _client()
    # clean existing
    try:
        existing = client.containers.get(settings.CF_TUNNEL_CONTAINER)
        existing.stop(timeout=5)
        existing.remove()
    except NotFound:
        pass
    # pull latest
    client.images.pull(settings.CF_TUNNEL_IMAGE)
    volumes = {}
    if settings.CF_TUNNEL_DIR:
        volumes[settings.CF_TUNNEL_DIR] = {"bind": "/etc/cloudflared", "mode": "rw"}
    container = client.containers.run(
        settings.CF_TUNNEL_IMAGE,
        tunnel_command(token),
        name=settings.CF_TUNNEL_CONTAINER,
        detach=True,
        restart_policy={"Name": "unless-stopped"},
        network_mode=settings.CF_TUNNEL_NETWORK,
        volumes=volumes,
        environment={"TUNNEL_TOKEN": token},
    )
    return {"id": container.id, "status": container.status}


def stop_tunnel() -> dict:
    client = _client()
    try:
        c = client.containers.get(settings.CF_TUNNEL_CONTAINER)
        c.stop(timeout=5)
        c.remove()
        return {"status": "stopped"}
    except NotFound:
        return {"status": "not_found"}


def tunnel_status() -> dict:
    client = _client()
    try:
        c = client.containers.get(settings.CF_TUNNEL_CONTAINER)
        c.reload()
        logs = c.logs(tail=20).decode("utf-8", errors="ignore") if c.status == "running" else ""
        return {"status": c.status, "id": c.id, "logs": logs}
    except NotFound:
        return {"status": "not_found"}
    except APIError as exc:
        return {"status": "error", "error": str(exc)}
