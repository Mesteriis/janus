import docker
from docker.errors import NotFound, APIError

from .docker_labels import compose_labels
from . import settings


def _client():
    return docker.from_env()


def tunnel_command(token: str) -> list[str]:
    return ["tunnel", "--no-autoupdate", "run", "--token", token]


def start_tunnel(token: str | None = None, container_name: str | None = None) -> dict:
    token = token or settings.CLOUDFLARE_TUNNEL_TOKEN
    if not token:
        raise ValueError("CLOUDFLARE_TUNNEL_TOKEN is empty")
    name = (container_name or settings.CF_TUNNEL_CONTAINER).strip() or settings.CF_TUNNEL_CONTAINER
    client = _client()
    # clean existing (force by exact name)
    api = getattr(client, "api", None)
    if api is not None and hasattr(api, "remove_container"):
        try:
            api.remove_container(name, force=True)
        except NotFound:
            pass
        except APIError as exc:
            if getattr(exc, "status_code", None) != 404:
                raise
    else:
        try:
            existing = client.containers.get(name)
            try:
                existing.remove(force=True)
            except TypeError:
                existing.remove()
        except NotFound:
            pass
        except APIError as exc:
            if getattr(exc, "status_code", None) != 404:
                raise
    # Equivalent to:
    # docker run -d --name <name> cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <token>
    client.images.pull(settings.CF_TUNNEL_IMAGE)
    container = client.containers.run(
        image=settings.CF_TUNNEL_IMAGE,
        command=tunnel_command(token),
        name=name,
        detach=True,
        labels=compose_labels("cloudflared", kind="cloudflare-tunnel"),
    )
    container.reload()
    return {"id": container.id, "status": container.status, "container_name": name}


def stop_tunnel() -> dict:
    client = _client()
    try:
        c = client.containers.get(settings.CF_TUNNEL_CONTAINER)
        c.stop(timeout=5)
        c.remove()
        return {"status": "stopped"}
    except NotFound:
        return {"status": "not_found"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


def stop_tunnel_container(container_name: str) -> dict:
    client = _client()
    clean_name = (container_name or "").strip()
    if not clean_name:
        return {"status": "not_found", "container_name": ""}
    try:
        c = client.containers.get(clean_name)
        c.remove(force=True)
        return {"status": "removed", "container_name": clean_name}
    except NotFound:
        return {"status": "not_found", "container_name": clean_name}


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
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}
