from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import docker
from docker.errors import APIError, NotFound

from ..docker_labels import compose_labels
from .. import settings
from .errors import ServiceError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _vpn_root() -> Path:
    return Path(settings.VPN_DATA_DIR)


def _vpn_host_root() -> Path:
    root = _vpn_root()
    try:
        container_id = Path("/etc/hostname").read_text(encoding="utf-8").strip()
        if not container_id:
            return root
        client = _docker_client()
        container = client.containers.get(container_id)
        mounts = (container.attrs.get("Mounts") or []) if getattr(container, "attrs", None) else []
        root_text = root.as_posix().rstrip("/")
        for mount in mounts:
            source = str(mount.get("Source") or "").strip()
            destination = str(mount.get("Destination") or "").strip()
            if not source or not destination:
                continue
            destination_text = Path(destination).as_posix().rstrip("/")
            if root_text == destination_text:
                return Path(source)
            prefix = destination_text + "/"
            if root_text.startswith(prefix):
                suffix = root_text[len(prefix) :]
                return Path(source) / suffix
    except Exception:
        # Fallback to current path when container mount metadata is unavailable.
        return root
    return root


def _to_host_path(path: Path) -> Path:
    root = _vpn_root()
    try:
        rel = path.relative_to(root)
    except ValueError:
        return path
    return _vpn_host_root() / rel


def _state_path() -> Path:
    return Path(settings.VPN_STATE_FILE)


def _servers_dir() -> Path:
    return _vpn_root() / "servers"


def _links_dir() -> Path:
    return _vpn_root() / "links"


def _archive_dir() -> Path:
    return _vpn_root() / "archive"


def _server_dir(server_id: str) -> Path:
    return _servers_dir() / server_id


def _server_clients_dir(server_id: str) -> Path:
    return _server_dir(server_id) / "clients"


def _container_name(server_id: str) -> str:
    return f"{settings.VPN_CONTAINER_PREFIX}-{server_id}"


def _link_container_name(link_id: str) -> str:
    return f"{settings.VPN_CONTAINER_PREFIX}-client-{link_id}"


def _endpoint_for_port(port: int) -> str:
    configured = (settings.VPN_PUBLIC_ENDPOINT or "").strip()
    if configured:
        return configured if ":" in configured else f"{configured}:{port}"
    return f"<PUBLIC_IP_OR_DNS>:{port}"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {"version": 1, "servers": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ServiceError(500, f"Invalid VPN state file: {exc}")
    if not isinstance(data, dict):
        raise ServiceError(500, "Invalid VPN state format")
    if not isinstance(data.get("servers"), list):
        data["servers"] = []
    if not isinstance(data.get("links"), list):
        data["links"] = []
    data.setdefault("version", 1)
    return data


def _save_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _docker_client():
    return docker.from_env()


def _wg_container_security_kwargs() -> dict[str, Any]:
    # Keep WG privileged enough for interface/routing ops, but never use host
    # network namespace to avoid mutating host routing.
    return {
        "cap_add": ["NET_ADMIN", "SYS_MODULE"],
        "privileged": True,
    }


def _remove_container(container_name: str) -> dict[str, str]:
    client = _docker_client()
    try:
        c = client.containers.get(container_name)
        c.remove(force=True)
        return {"status": "removed", "container_name": container_name}
    except NotFound:
        return {"status": "not_found", "container_name": container_name}
    except APIError as exc:
        # docker can return "removal already in progress"
        if "removal of container" in str(exc).lower():
            return {"status": "removing", "container_name": container_name}
        raise


def _run_wg_command(command: str, env: dict[str, str] | None = None) -> str:
    client = _docker_client()
    try:
        output = client.containers.run(
            image=settings.VPN_WG_IMAGE,
            entrypoint="/bin/sh",
            command=["-lc", command],
            remove=True,
            environment=env or {},
        )
    except Exception as exc:
        raise ServiceError(500, f"WireGuard helper failed: {exc}")
    if isinstance(output, (bytes, bytearray)):
        return bytes(output).decode("utf-8", errors="ignore").strip()
    return str(output).strip()


def _generate_keypair() -> tuple[str, str]:
    private_key = _run_wg_command("wg genkey")
    if not private_key:
        raise ServiceError(500, "Failed to generate WireGuard private key")
    public_key = _run_wg_command("printf %s \"$WG_PRIVATE_KEY\" | wg pubkey", env={"WG_PRIVATE_KEY": private_key})
    if not public_key:
        raise ServiceError(500, "Failed to generate WireGuard public key")
    return private_key, public_key


def _next_free_port(servers: list[dict[str, Any]]) -> int:
    used = {int(s.get("listen_port") or 0) for s in servers}
    port = int(settings.VPN_PORT_BASE)
    while port in used:
        port += 1
    return port


def _is_port_bind_conflict(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "address already in use" in text
        or "failed to bind host port" in text
        or "port is already allocated" in text
    )


def _next_free_subnet(servers: list[dict[str, Any]]) -> tuple[str, str]:
    used_octets: set[int] = set()
    for server in servers:
        cidr = str(server.get("subnet_cidr") or "")
        parts = cidr.split(".")
        if len(parts) >= 3:
            try:
                used_octets.add(int(parts[2]))
            except Exception:
                continue
    base = str(settings.VPN_SUBNET_BASE or "10.66").strip()
    for octet in range(10, 250):
        if octet in used_octets:
            continue
        subnet = f"{base}.{octet}.0/24"
        server_addr = f"{base}.{octet}.1/24"
        return subnet, server_addr
    raise ServiceError(500, "No free VPN subnet available")


def _next_client_ip(server: dict[str, Any]) -> str:
    subnet = str(server.get("subnet_cidr") or "10.66.10.0/24")
    prefix = ".".join(subnet.split(".")[:3])
    used = {"1"}
    for client in server.get("clients", []):
        addr = str(client.get("address") or "")
        host_part = addr.split("/")[0].split(".")[-1] if addr else ""
        if host_part:
            used.add(host_part)
    for last in range(2, 250):
        if str(last) not in used:
            return f"{prefix}.{last}/32"
    raise ServiceError(500, "No free client IP in VPN subnet")


def _build_server_config(server: dict[str, Any], server_private_key: str) -> str:
    lines = [
        "[Interface]",
        f"Address = {server['server_address']}",
        f"ListenPort = {server['listen_port']}",
        f"PrivateKey = {server_private_key}",
        "",
    ]
    for client in server.get("clients", []):
        lines.extend(
            [
                "[Peer]",
                f"PublicKey = {client['public_key']}",
                f"AllowedIPs = {client['address']}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _build_client_config(server: dict[str, Any], client_private_key: str, client_address: str) -> str:
    endpoint = str(server.get("endpoint") or _endpoint_for_port(int(server["listen_port"])))
    return (
        "[Interface]\n"
        f"PrivateKey = {client_private_key}\n"
        f"Address = {client_address}\n"
        "DNS = 1.1.1.1\n\n"
        "[Peer]\n"
        f"PublicKey = {server['server_public_key']}\n"
        f"Endpoint = {endpoint}\n"
        "AllowedIPs = 0.0.0.0/0, ::/0\n"
        "PersistentKeepalive = 25\n"
    )


def _find_server(state: dict[str, Any], server_id: str) -> dict[str, Any]:
    for server in state.get("servers", []):
        if str(server.get("id")) == server_id:
            return server
    raise ServiceError(404, "VPN server not found")


def _find_client(server: dict[str, Any], client_id: str) -> dict[str, Any]:
    for client in server.get("clients", []):
        if str(client.get("id")) == client_id:
            return client
    raise ServiceError(404, "VPN client not found")


def _find_link(state: dict[str, Any], link_id: str) -> dict[str, Any]:
    for link in state.get("links", []):
        if str(link.get("id")) == link_id:
            return link
    raise ServiceError(404, "VPN link not found")


def _server_public_payload(server: dict[str, Any]) -> dict[str, Any]:
    clients = [
        {
            "id": c.get("id"),
            "name": c.get("name"),
            "address": c.get("address"),
            "created_at": c.get("created_at"),
            "config_path": c.get("config_path"),
        }
        for c in server.get("clients", [])
    ]
    return {
        "id": server.get("id"),
        "name": server.get("name"),
        "created_at": server.get("created_at"),
        "updated_at": server.get("updated_at"),
        "listen_port": server.get("listen_port"),
        "subnet_cidr": server.get("subnet_cidr"),
        "server_address": server.get("server_address"),
        "endpoint": server.get("endpoint"),
        "running": bool(server.get("running")),
        "container_name": server.get("container_name"),
        "server_public_key": server.get("server_public_key"),
        "clients": clients,
        "instructions": (
            "1) Импортируйте клиентский .conf в приложение WireGuard.\n"
            "2) Подключитесь к VPN.\n"
            "3) Откройте Caddy через адрес сервера внутри VPN (обычно 10.66.x.1)."
        ),
    }


def _link_public_payload(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": link.get("id"),
        "name": link.get("name"),
        "created_at": link.get("created_at"),
        "updated_at": link.get("updated_at"),
        "interface": link.get("interface"),
        "running": bool(link.get("running")),
        "container_name": link.get("container_name"),
        "config_path": link.get("config_path"),
        "instructions": (
            "1) Вставьте client-конфиг от удаленного WireGuard сервера.\n"
            "2) Подключите линк.\n"
            "3) Весь TCP-трафик из этого WG-интерфейса редиректится в локальный Caddy :80."
        ),
    }


def _normalize_iface(seed: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9]+", "", seed.lower())
    return f"jwg{raw[:8] or 'link'}"


def _resolve_caddy_target() -> tuple[str, int]:
    try:
        client = _docker_client()
        caddy = client.containers.get("janus-caddy")
        networks = (caddy.attrs.get("NetworkSettings", {}) or {}).get("Networks", {}) or {}
        for net in networks.values():
            ip = str((net or {}).get("IPAddress") or "").strip()
            if ip:
                return ip, 80
    except Exception:
        pass
    return "host.docker.internal", 18080


def _inject_redirect_rules(config_text: str, iface: str, caddy_host: str, caddy_port: int) -> str:
    post_up_dnat = (
        f"PostUp = iptables -t nat -A PREROUTING -i {iface} -p tcp -j DNAT --to-destination {caddy_host}:{caddy_port}"
    )
    post_down_dnat = (
        f"PostDown = iptables -t nat -D PREROUTING -i {iface} -p tcp -j DNAT --to-destination {caddy_host}:{caddy_port}"
    )
    post_up_masq = f"PostUp = iptables -t nat -A POSTROUTING -o eth0 -p tcp -d {caddy_host} --dport {caddy_port} -j MASQUERADE"
    post_down_masq = (
        f"PostDown = iptables -t nat -D POSTROUTING -o eth0 -p tcp -d {caddy_host} --dport {caddy_port} -j MASQUERADE"
    )
    subnet_match = re.search(r"(?mi)^Address\s*=\s*((\d+\.\d+\.\d+)\.\d+)/(?:\d+)\s*$", config_text)
    route_cidr = f"{subnet_match.group(2)}.0/24" if subnet_match else ""
    post_up_route = f"PostUp = ip route replace {route_cidr} dev {iface}" if route_cidr else ""
    post_down_route = f"PostDown = ip route del {route_cidr} dev {iface} || true" if route_cidr else ""
    table_off = "Table = off"
    lines = config_text.replace("\r\n", "\n").split("\n")
    required_rules = [post_up_dnat, post_down_dnat, post_up_masq, post_down_masq]
    if post_up_route and post_down_route:
        required_rules.extend([post_up_route, post_down_route])
    has_post_rules = all(any(rule in line for line in lines) for rule in required_rules)
    has_table_off = any(line.strip().lower() == "table = off" for line in lines)
    if has_post_rules and has_table_off:
        return config_text if config_text.endswith("\n") else config_text + "\n"
    out: list[str] = []
    inserted = False
    in_interface = False
    table_inserted = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            if in_interface and not inserted:
                if not has_table_off and not table_inserted:
                    out.append(table_off)
                    table_inserted = True
                out.append(post_up_dnat)
                out.append(post_down_dnat)
                out.append(post_up_masq)
                out.append(post_down_masq)
                if post_up_route and post_down_route:
                    out.append(post_up_route)
                    out.append(post_down_route)
                inserted = True
            in_interface = stripped.lower() == "[interface]"
        if in_interface and stripped.lower().startswith("dns ="):
            continue
        out.append(line)
        if in_interface and not has_table_off and not table_inserted:
            # Put Table=off inside [Interface] before first peer block.
            out.append(table_off)
            table_inserted = True
    if in_interface and not inserted:
        if not has_table_off and not table_inserted:
            out.append(table_off)
        out.append(post_up_dnat)
        out.append(post_down_dnat)
        out.append(post_up_masq)
        out.append(post_down_masq)
        if post_up_route and post_down_route:
            out.append(post_up_route)
            out.append(post_down_route)
    rendered = "\n".join(out).strip() + "\n"
    return rendered


def _link_dir(link_id: str) -> Path:
    return _links_dir() / link_id


def _render_link_files(link: dict[str, Any]) -> None:
    ldir = _link_dir(str(link["id"]))
    ldir.mkdir(parents=True, exist_ok=True)
    iface = str(link["interface"])
    raw_path = ldir / "raw.conf"
    patched_path = ldir / f"{iface}.conf"
    _write_text(raw_path, str(link.get("raw_config") or ""))
    caddy_host, caddy_port = _resolve_caddy_target()
    patched = _inject_redirect_rules(str(link.get("raw_config") or ""), iface, caddy_host=caddy_host, caddy_port=caddy_port)
    _write_text(patched_path, patched)
    try:
        patched_path.chmod(0o600)
    except Exception:
        pass
    link["config_path"] = str(patched_path)


def _start_link_container(link: dict[str, Any]) -> dict[str, Any]:
    link_id = str(link["id"])
    iface = str(link["interface"])
    container_name = _link_container_name(link_id)
    _remove_container(container_name)
    _render_link_files(link)
    ldir = _link_dir(link_id)
    ldir_host = _to_host_path(ldir)
    client = _docker_client()
    try:
        container = client.containers.run(
            image=settings.VPN_WG_IMAGE,
            entrypoint="/bin/sh",
            command=[
                "-lc",
                (
                    "ip link delete {iface} >/dev/null 2>&1 || true; "
                    "sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true; "
                    "wg-quick up /config/{iface}.conf && tail -f /dev/null"
                ).format(iface=iface),
            ],
            name=container_name,
            detach=True,
            volumes={str(ldir_host): {"bind": "/config", "mode": "rw"}},
            labels=compose_labels("vpn", kind="wireguard-link", extra={"io.janus.vpn.link_id": link_id}),
            **_wg_container_security_kwargs(),
        )
        container.reload()
    except Exception as exc:
        raise ServiceError(500, f"Failed to start VPN link: {exc}")
    link["running"] = container.status == "running"
    link["container_name"] = container_name
    link["updated_at"] = _now()
    return {"id": container.id, "status": container.status, "container_name": container_name}


def _stop_link_container(link: dict[str, Any]) -> dict[str, str]:
    container_name = str(link.get("container_name") or _link_container_name(str(link["id"])))
    iface = str(link.get("interface") or "wg0")
    client = _docker_client()
    try:
        c = client.containers.get(container_name)
        try:
            c.exec_run(["/bin/sh", "-lc", f"wg-quick down {iface} >/dev/null 2>&1 || true"])
        except Exception:
            pass
        c.remove(force=True)
        result = {"status": "removed", "container_name": container_name}
    except NotFound:
        result = {"status": "not_found", "container_name": container_name}
    except APIError as exc:
        if "removal of container" in str(exc).lower():
            result = {"status": "removing", "container_name": container_name}
        else:
            raise
    link["running"] = False
    link["updated_at"] = _now()
    return result


def _render_server_files(server: dict[str, Any]) -> None:
    sid = str(server["id"])
    sdir = _server_dir(sid)
    cdir = _server_clients_dir(sid)
    sdir.mkdir(parents=True, exist_ok=True)
    cdir.mkdir(parents=True, exist_ok=True)

    private_key = str(server["server_private_key"])
    _write_text(sdir / "private.key", private_key + "\n")
    _write_text(sdir / "public.key", str(server["server_public_key"]) + "\n")
    _write_text(sdir / "wg0.conf", _build_server_config(server, private_key))

    for client in server.get("clients", []):
        config = _build_client_config(server, str(client["private_key"]), str(client["address"]))
        path = cdir / f"{client['id']}.conf"
        _write_text(path, config)
        client["config_path"] = str(path)


def _start_container(server: dict[str, Any]) -> dict[str, Any]:
    sid = str(server["id"])
    container_name = _container_name(sid)
    _remove_container(container_name)

    _render_server_files(server)

    client = _docker_client()
    server_path = _server_dir(sid)
    server_path_host = _to_host_path(server_path)
    try:
        container = client.containers.run(
            image=settings.VPN_WG_IMAGE,
            entrypoint="/bin/sh",
            command=[
                "-lc",
                "ip link delete wg0 >/dev/null 2>&1 || true; "
                "sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true; "
                "wg-quick up /config/wg0.conf && tail -f /dev/null",
            ],
            name=container_name,
            detach=True,
            volumes={str(server_path_host): {"bind": "/config", "mode": "rw"}},
            ports={f"{int(server['listen_port'])}/udp": int(server["listen_port"])},
            labels=compose_labels("vpn", kind="wireguard-server", extra={"io.janus.vpn.server_id": sid}),
            **_wg_container_security_kwargs(),
        )
        container.reload()
    except Exception as exc:
        raise ServiceError(500, f"Failed to start VPN container: {exc}")

    server["running"] = container.status == "running"
    server["container_name"] = container_name
    server["updated_at"] = _now()
    return {"id": container.id, "status": container.status, "container_name": container_name}


def _stop_container(server: dict[str, Any]) -> dict[str, str]:
    container_name = str(server.get("container_name") or _container_name(str(server["id"])))
    client = _docker_client()
    try:
        c = client.containers.get(container_name)
        try:
            c.exec_run(["/bin/sh", "-lc", "wg-quick down wg0 >/dev/null 2>&1 || true"])
        except Exception:
            pass
        c.remove(force=True)
        result = {"status": "removed", "container_name": container_name}
    except NotFound:
        result = {"status": "not_found", "container_name": container_name}
    server["running"] = False
    server["updated_at"] = _now()
    return result


def get_status() -> dict[str, Any]:
    state = _load_state()
    servers = [_server_public_payload(s) for s in state.get("servers", [])]
    links = [_link_public_payload(l) for l in state.get("links", [])]
    return {
        "status": "configured" if (servers or links) else "not_configured",
        "message": "WireGuard серверы готовы" if (servers or links) else "VPN серверы не созданы",
        "data_dir": str(_vpn_root()),
        "state_file": str(_state_path()),
        "servers": servers,
        "links": links,
    }


def create_server(name: str = "") -> dict[str, Any]:
    state = _load_state()
    servers = state.setdefault("servers", [])
    server_id = str(uuid4())
    port = _next_free_port(servers)
    subnet_cidr, server_address = _next_free_subnet(servers)
    server_private_key, server_public_key = _generate_keypair()

    server = {
        "id": server_id,
        "name": (name or f"VPN Server {len(servers) + 1}").strip(),
        "created_at": _now(),
        "updated_at": _now(),
        "listen_port": port,
        "subnet_cidr": subnet_cidr,
        "server_address": server_address,
        "endpoint": _endpoint_for_port(port),
        "running": False,
        "container_name": _container_name(server_id),
        "server_private_key": server_private_key,
        "server_public_key": server_public_key,
        "clients": [],
    }
    servers.append(server)
    _save_state(state)

    # Improvement: create first client automatically.
    add_client(server_id, "default-client", save_after=True)

    max_retries = 20
    for _ in range(max_retries):
        try:
            return start_server(server_id)
        except ServiceError as exc:
            if not _is_port_bind_conflict(exc):
                raise
            latest_state = _load_state()
            latest_server = _find_server(latest_state, server_id)
            latest_server["listen_port"] = int(latest_server["listen_port"]) + 1
            latest_server["endpoint"] = _endpoint_for_port(int(latest_server["listen_port"]))
            latest_server["running"] = False
            latest_server["updated_at"] = _now()
            _save_state(latest_state)
            _render_server_files(latest_server)
    raise ServiceError(500, "Failed to allocate free UDP port for VPN server")


def start_server(server_id: str) -> dict[str, Any]:
    state = _load_state()
    server = _find_server(state, server_id)
    docker_info = _start_container(server)
    _save_state(state)
    payload = get_status()
    payload["docker"] = docker_info
    return payload


def stop_server(server_id: str) -> dict[str, Any]:
    state = _load_state()
    server = _find_server(state, server_id)
    docker_info = _stop_container(server)
    _save_state(state)
    payload = get_status()
    payload["docker"] = docker_info
    return payload


def delete_server(server_id: str) -> dict[str, Any]:
    state = _load_state()
    server = _find_server(state, server_id)
    _stop_container(server)
    servers = [s for s in state.get("servers", []) if str(s.get("id")) != server_id]
    state["servers"] = servers
    _save_state(state)

    source = _server_dir(server_id)
    if source.exists():
        _archive_dir().mkdir(parents=True, exist_ok=True)
        target = _archive_dir() / f"{server_id}-{int(datetime.now().timestamp())}"
        shutil.move(str(source), str(target))
    return get_status()


def create_link(name: str, config: str) -> dict[str, Any]:
    clean_config = str(config or "").strip()
    if not clean_config:
        raise ServiceError(400, "WireGuard config is required")
    if "[Interface]" not in clean_config or "[Peer]" not in clean_config:
        raise ServiceError(400, "Invalid WireGuard config")

    state = _load_state()
    links = state.setdefault("links", [])
    link_id = str(uuid4())
    link = {
        "id": link_id,
        "name": (name or f"VPN Link {len(links) + 1}").strip(),
        "created_at": _now(),
        "updated_at": _now(),
        "interface": _normalize_iface(link_id.replace("-", "")),
        "running": False,
        "container_name": _link_container_name(link_id),
        "raw_config": clean_config + ("\n" if not clean_config.endswith("\n") else ""),
        "config_path": "",
    }
    links.append(link)
    _save_state(state)
    return start_link(link_id)


def start_link(link_id: str) -> dict[str, Any]:
    state = _load_state()
    link = _find_link(state, link_id)
    docker_info = _start_link_container(link)
    _save_state(state)
    payload = get_status()
    payload["docker"] = docker_info
    return payload


def stop_link(link_id: str) -> dict[str, Any]:
    state = _load_state()
    link = _find_link(state, link_id)
    docker_info = _stop_link_container(link)
    _save_state(state)
    payload = get_status()
    payload["docker"] = docker_info
    return payload


def delete_link(link_id: str) -> dict[str, Any]:
    state = _load_state()
    link = _find_link(state, link_id)
    _stop_link_container(link)
    state["links"] = [l for l in state.get("links", []) if str(l.get("id")) != link_id]
    _save_state(state)

    source = _link_dir(link_id)
    if source.exists():
        _archive_dir().mkdir(parents=True, exist_ok=True)
        target = _archive_dir() / f"link-{link_id}-{int(datetime.now().timestamp())}"
        shutil.move(str(source), str(target))
    return get_status()


def get_link_config(link_id: str) -> dict[str, Any]:
    state = _load_state()
    link = _find_link(state, link_id)
    if not link.get("config_path"):
        _render_link_files(link)
        _save_state(state)
    path = Path(str(link.get("config_path") or ""))
    if not path.exists():
        raise ServiceError(404, "VPN link config not found")
    return {
        "link_id": link_id,
        "name": link.get("name"),
        "interface": link.get("interface"),
        "config_path": str(path),
        "config": path.read_text(encoding="utf-8"),
    }


def add_client(server_id: str, name: str = "", save_after: bool = False) -> dict[str, Any]:
    state = _load_state()
    server = _find_server(state, server_id)
    client_id = str(uuid4())
    client_private, client_public = _generate_keypair()
    client_address = _next_client_ip(server)
    client = {
        "id": client_id,
        "name": (name or f"client-{len(server.get('clients', [])) + 1}").strip(),
        "created_at": _now(),
        "address": client_address,
        "public_key": client_public,
        "private_key": client_private,
        "config_path": "",
    }
    server.setdefault("clients", []).append(client)
    server["updated_at"] = _now()
    _render_server_files(server)

    # If server is running, restart to apply peers.
    if server.get("running"):
        _stop_container(server)
        _start_container(server)

    _save_state(state)
    if save_after:
        return client
    payload = get_status()
    payload["client"] = {
        "id": client["id"],
        "name": client["name"],
        "address": client["address"],
        "config_path": client["config_path"],
    }
    return payload


def get_client_config(server_id: str, client_id: str) -> dict[str, Any]:
    state = _load_state()
    server = _find_server(state, server_id)
    client = _find_client(server, client_id)
    path = Path(str(client.get("config_path") or ""))
    if not path.exists():
        _render_server_files(server)
        _save_state(state)
        path = Path(str(client.get("config_path") or ""))
    if not path.exists():
        raise ServiceError(404, "Client config not found")
    return {
        "server_id": server_id,
        "client_id": client_id,
        "name": client.get("name"),
        "address": client.get("address"),
        "config_path": str(path),
        "config": path.read_text(encoding="utf-8"),
    }


def reconcile_on_startup() -> None:
    state = _load_state()
    changed = False
    for server in state.get("servers", []):
        try:
            if server.get("running"):
                _start_container(server)
            else:
                _stop_container(server)
            changed = True
        except Exception:
            server["running"] = False
            server["updated_at"] = _now()
            changed = True
    for link in state.get("links", []):
        try:
            if link.get("running"):
                _start_link_container(link)
            else:
                _stop_link_container(link)
            changed = True
        except Exception:
            link["running"] = False
            link["updated_at"] = _now()
            changed = True
    if changed:
        _save_state(state)
