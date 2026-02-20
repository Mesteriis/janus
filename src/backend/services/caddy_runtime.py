from __future__ import annotations

import json
import logging
import io
import os
import re
import threading
import time
import tarfile
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import docker
from docker.errors import APIError, NotFound

from ..core.config import get_settings
from ..caddyfile import write_default_caddyfile
from ..docker_labels import compose_labels
from ..storage import load_routes
from ..utils import ensure_parent
from .errors import ServiceError

logger = logging.getLogger(__name__)
_settings = get_settings()

RUNTIME_CONTAINER = os.getenv("CADDY_RUNTIME_CONTAINER", "janus-caddy")
RUNTIME_IMAGE = os.getenv("CADDY_RUNTIME_IMAGE", "janus/caddy-runtime:local")
RUNTIME_STATE_FILE = Path(os.getenv("CADDY_RUNTIME_STATE_FILE", str(_settings.caddyfile_path.parent / "runtime_state.json")))
RUNTIME_DATA_DIR = Path(os.getenv("CADDY_RUNTIME_DATA_DIR", str(_settings.caddyfile_path.parent / "runtime")))
RUNTIME_MONITOR_INTERVAL = int(os.getenv("CADDY_RUNTIME_MONITOR_INTERVAL", "10"))
RUNTIME_MAX_RESTARTS = int(os.getenv("CADDY_RUNTIME_MAX_RESTARTS", "5"))
RUNTIME_LOG_LIMIT = int(os.getenv("CADDY_RUNTIME_LOG_LIMIT", "800"))
RUNTIME_HTTP_PORT = int(os.getenv("CADDY_RUNTIME_HTTP_PORT", "18080"))
RUNTIME_HTTPS_PORT = int(os.getenv("CADDY_RUNTIME_HTTPS_PORT", "18443"))
RUNTIME_CADDYFILE_HOST_PATH = os.getenv("CADDY_RUNTIME_CADDYFILE_HOST_PATH", "").strip()

AVAILABLE_ADDONS: dict[str, dict[str, str]] = {
    "cloudflare_dns": {
        "module": "github.com/caddy-dns/cloudflare",
        "label": "Cloudflare DNS",
        "description": "DNS challenge для Let's Encrypt через Cloudflare API.",
    },
    "realip": {
        "module": "github.com/captncraig/caddy-realip",
        "label": "Real IP",
        "description": "Корректный client IP за reverse proxy/Cloudflare.",
    },
    "cache_handler": {
        "module": "github.com/caddyserver/cache-handler",
        "label": "Cache Handler",
        "description": "Кэширование ответов для статичных и проксируемых ресурсов.",
    },
    "replace_response": {
        "module": "github.com/caddyserver/replace-response",
        "label": "Replace Response",
        "description": "Замена текста/паттернов в ответах.",
    },
    "rate_limit": {
        "module": "github.com/mholt/caddy-ratelimit",
        "label": "Rate Limit",
        "description": "Ограничение частоты запросов.",
    },
}

PRESETS: dict[str, dict[str, Any]] = {
    "base": {
        "label": "Base",
        "description": "Рекомендуемый минимум для Cloudflare + reverse proxy.",
        "addons": ["cloudflare_dns", "realip"],
    },
    "security": {
        "label": "Security",
        "description": "Базовый security-слой с rate limit и transform.",
        "addons": ["realip", "rate_limit", "replace_response"],
    },
    "observability": {
        "label": "Observability",
        "description": "Кэширование и диагностика поведения upstream.",
        "addons": ["realip", "cache_handler"],
    },
}


@dataclass
class InstallState:
    in_progress: bool = False
    progress: int = 0
    step: str = "idle"
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    build_id: str = ""


_lock = threading.RLock()
_state: dict[str, Any] | None = None
_install = InstallState()
_install_thread: threading.Thread | None = None
_monitor_thread: threading.Thread | None = None
_monitor_stop = threading.Event()
_logs: deque[dict[str, Any]] = deque(maxlen=RUNTIME_LOG_LIMIT)
_log_counter = 0


def _docker_client():
    return docker.from_env()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _append_log(source: str, message: str, level: str = "info") -> None:
    global _log_counter
    text = str(message or "").strip()
    if not text:
        return
    with _lock:
        _log_counter += 1
        _logs.append(
            {
                "id": _log_counter,
                "ts": _now_iso(),
                "source": source,
                "level": level,
                "message": text,
            }
        )


def _load_state() -> dict[str, Any]:
    global _state
    with _lock:
        if _state is not None:
            return _state
        try:
            data = json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {}
        except json.JSONDecodeError:
            data = {}
        _state = {
            "selected_addons": list(data.get("selected_addons") or []),
            "manual_stop": bool(data.get("manual_stop", False)),
            "auto_restart_count": int(data.get("auto_restart_count", 0)),
            "history": list(data.get("history") or []),
            "last_install": data.get("last_install") or None,
            "profiles": list(data.get("profiles") or []),
        }
        return _state


def _save_state() -> None:
    with _lock:
        state = _load_state().copy()
    ensure_parent(str(RUNTIME_STATE_FILE))
    RUNTIME_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _push_history(action: str, success: bool, message: str, addons: list[str] | None = None, duration_ms: int | None = None) -> None:
    with _lock:
        state = _load_state()
        history = list(state.get("history") or [])
        history.insert(
            0,
            {
                "ts": _now_iso(),
                "action": action,
                "success": bool(success),
                "message": str(message or ""),
                "addons": list(addons or []),
                "duration_ms": duration_ms,
            },
        )
        state["history"] = history[:30]
    _save_state()


def _new_build_id() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")


def _build_artifacts(build_id: str) -> tuple[Path, Path, Path]:
    root = RUNTIME_DATA_DIR / "builds" / build_id
    return root, root / "Dockerfile", root / "build.log"


def _push_profile(build_id: str, addons: list[str]) -> None:
    with _lock:
        state = _load_state()
        profiles = list(state.get("profiles") or [])
        profiles = [item for item in profiles if item.get("build_id") != build_id]
        profiles.insert(
            0,
            {
                "build_id": build_id,
                "addons": list(addons),
                "ts": _now_iso(),
                "image": RUNTIME_IMAGE,
            },
        )
        state["profiles"] = profiles[:20]
    _save_state()


def _validate_addons(addons: list[str]) -> list[str]:
    clean = []
    seen = set()
    for item in addons:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        if key not in AVAILABLE_ADDONS:
            raise ServiceError(400, f"Unsupported addon: {key}")
        clean.append(key)
        seen.add(key)
    return clean


def _build_dockerfile(addons: list[str]) -> str:
    modules = [AVAILABLE_ADDONS[item]["module"] for item in addons]
    lines = [
        "FROM caddy:2-builder AS builder",
        "RUN xcaddy build \\",
    ]
    if modules:
        for index, module in enumerate(modules):
            suffix = " \\" if index < len(modules) - 1 else ""
            lines.append(f"  --with {module}{suffix}")
    else:
        lines[-1] = "RUN xcaddy build"
    lines.extend(
        [
            "",
            "FROM caddy:2",
            "COPY --from=builder /usr/bin/caddy /usr/bin/caddy",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_build_progress(line: str) -> int | None:
    match = re.search(r"STEP\s+(\d+)\/(\d+)", line)
    if not match:
        return None
    current = int(match.group(1))
    total = int(match.group(2))
    if total <= 0:
        return None
    ratio = current / total
    return min(70, max(15, int(15 + ratio * 55)))


def _run_build(addons: list[str], build_id: str) -> None:
    _install.step = "build"
    _install.progress = 10
    build_dir, dockerfile_path, build_log_path = _build_artifacts(build_id)
    build_dir.mkdir(parents=True, exist_ok=True)
    dockerfile_path.write_text(_build_dockerfile(addons), encoding="utf-8")
    ensure_parent(str(build_log_path))

    context_path = str(_settings.project_root)
    dockerfile_rel = str(dockerfile_path.relative_to(_settings.project_root))
    _append_log("build", f"Building image {RUNTIME_IMAGE} from {dockerfile_rel}")

    client = _docker_client()
    with build_log_path.open("a", encoding="utf-8") as build_log:
        try:
            stream = client.api.build(
                path=context_path,
                dockerfile=dockerfile_rel,
                tag=RUNTIME_IMAGE,
                rm=True,
                decode=True,
            )
            for chunk in stream:
                line = ""
                if isinstance(chunk, dict):
                    if chunk.get("error"):
                        line = str(chunk.get("error"))
                        _append_log("build", line, level="error")
                        build_log.write(line + "\n")
                        raise ServiceError(500, line)
                    if chunk.get("stream"):
                        line = str(chunk.get("stream")).rstrip()
                    elif chunk.get("status"):
                        line = str(chunk.get("status")).rstrip()
                else:
                    line = str(chunk).rstrip()

                if not line:
                    continue

                _append_log("build", line)
                build_log.write(line + "\n")
                progress = _parse_build_progress(line)
                if progress is not None:
                    _install.progress = progress
        except APIError as exc:
            raise ServiceError(500, str(exc))

    _install.progress = 75


def _ensure_runtime_dirs() -> tuple[Path, Path]:
    data_dir = RUNTIME_DATA_DIR / "caddy-data"
    config_dir = RUNTIME_DATA_DIR / "caddy-config"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    return data_dir, config_dir


def _sync_caddyfile_into_container(container) -> None:
    source = _settings.caddyfile_path
    if RUNTIME_CADDYFILE_HOST_PATH:
        source = Path(RUNTIME_CADDYFILE_HOST_PATH)
    if not source.exists():
        write_default_caddyfile(load_routes())

    content = source.read_text(encoding="utf-8")
    encoded = content.encode("utf-8")

    archive_buf = io.BytesIO()
    with tarfile.open(fileobj=archive_buf, mode="w") as tar:
        info = tarfile.TarInfo(name="Caddyfile")
        info.size = len(encoded)
        tar.addfile(info, io.BytesIO(encoded))
    archive_buf.seek(0)
    ok = container.put_archive("/etc/caddy", archive_buf.getvalue())
    if not ok:
        raise ServiceError(500, "Failed to copy Caddyfile into runtime container")


def _container_exists(client) -> tuple[bool, Any | None]:
    try:
        container = client.containers.get(RUNTIME_CONTAINER)
        return True, container
    except NotFound:
        return False, None


def _create_or_start_container(recreate: bool = False) -> dict[str, Any]:
    client = _docker_client()
    exists, container = _container_exists(client)

    if recreate and exists and container is not None:
        container.remove(force=True)
        exists = False
        container = None

    if not _settings.caddyfile_path.exists():
        write_default_caddyfile(load_routes())

    data_volume = f"{RUNTIME_CONTAINER}-data"
    config_volume = f"{RUNTIME_CONTAINER}-config"
    volumes = {
        data_volume: {"bind": "/data", "mode": "rw"},
        config_volume: {"bind": "/config", "mode": "rw"},
    }

    if not exists:
        ports = {"80/tcp": RUNTIME_HTTP_PORT, "443/tcp": RUNTIME_HTTPS_PORT}
        container = client.containers.run(
            image=RUNTIME_IMAGE,
            command=["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"],
            name=RUNTIME_CONTAINER,
            detach=True,
            restart_policy={"Name": "unless-stopped"},
            volumes=volumes,
            ports=ports,
            labels=compose_labels("caddy", kind="caddy-runtime"),
        )
    else:
        assert container is not None
        container.start()
        _sync_caddyfile_into_container(container)
        container.restart(timeout=10)

    assert container is not None
    if not exists:
        _sync_caddyfile_into_container(container)
        container.restart(timeout=10)
    container.reload()
    return {
        "id": container.id,
        "status": container.status,
        "container_name": RUNTIME_CONTAINER,
        "image": RUNTIME_IMAGE,
    }


def _inspect_container() -> dict[str, Any]:
    client = _docker_client()
    try:
        container = client.containers.get(RUNTIME_CONTAINER)
    except NotFound:
        return {"exists": False, "status": "not_found"}
    except APIError as exc:
        return {"exists": False, "status": "error", "error": str(exc)}

    container.reload()
    attrs = getattr(container, "attrs", {}) or {}
    state = attrs.get("State", {}) or {}
    health = (state.get("Health") or {}).get("Status")
    return {
        "exists": True,
        "id": container.id,
        "status": container.status,
        "created": attrs.get("Created"),
        "image": (attrs.get("Config") or {}).get("Image") or RUNTIME_IMAGE,
        "health": health or "unknown",
        "container_name": RUNTIME_CONTAINER,
    }


def _read_runtime_logs(limit: int = 200) -> list[dict[str, Any]]:
    client = _docker_client()
    try:
        container = client.containers.get(RUNTIME_CONTAINER)
    except (NotFound, APIError):
        return []

    try:
        raw = container.logs(tail=max(1, min(500, limit)), timestamps=True)
    except TypeError:
        raw = container.logs(tail=max(1, min(500, limit)))
    except APIError:
        return []

    text = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        ts = _now_iso()
        message = line
        if " " in line and line[:4].isdigit():
            first, rest = line.split(" ", 1)
            ts = first
            message = rest
        rows.append(
            {
                "id": 0,
                "ts": ts,
                "source": "runtime",
                "level": "info",
                "message": message,
            }
        )
    return rows[-limit:]


def _set_install_error(message: str) -> None:
    _install.error = str(message or "Unknown error")
    _install.step = "error"
    _install.progress = 100
    _install.finished_at = time.time()


def _install_worker(addons: list[str], action: str, rollback_from: str = "") -> None:
    started = time.time()
    build_id = _install.build_id or _new_build_id()
    _append_log("system", f"{action} started. addons={addons} build_id={build_id}")
    try:
        _run_build(addons, build_id=build_id)
        _install.step = "starting"
        _install.progress = 85
        result = _create_or_start_container(recreate=True)
        _append_log("system", f"Container started: {result.get('container_name')} ({result.get('status')})")
        _install.step = "done"
        _install.progress = 100
        _install.error = ""
        _install.finished_at = time.time()

        with _lock:
            state = _load_state()
            state["selected_addons"] = list(addons)
            state["manual_stop"] = False
            state["last_install"] = {
                "ts": _now_iso(),
                "success": True,
                "addons": list(addons),
                "image": RUNTIME_IMAGE,
                "container": RUNTIME_CONTAINER,
                "build_id": build_id,
                "action": action,
                "rollback_from": rollback_from or None,
            }
        _save_state()
        _push_profile(build_id=build_id, addons=addons)

        duration = int((time.time() - started) * 1000)
        _push_history(action, True, "Container built and started", addons=addons, duration_ms=duration)
    except ServiceError as exc:
        _append_log("build", exc.detail, level="error")
        _set_install_error(exc.detail)
        with _lock:
            state = _load_state()
            state["last_install"] = {
                "ts": _now_iso(),
                "success": False,
                "addons": list(addons),
                "image": RUNTIME_IMAGE,
                "container": RUNTIME_CONTAINER,
                "build_id": build_id,
                "action": action,
                "rollback_from": rollback_from or None,
                "error": exc.detail,
            }
        _save_state()
        duration = int((time.time() - started) * 1000)
        _push_history(action, False, exc.detail, addons=addons, duration_ms=duration)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled caddy runtime install error")
        _append_log("build", str(exc), level="error")
        _set_install_error(str(exc))
        with _lock:
            state = _load_state()
            state["last_install"] = {
                "ts": _now_iso(),
                "success": False,
                "addons": list(addons),
                "image": RUNTIME_IMAGE,
                "container": RUNTIME_CONTAINER,
                "build_id": build_id,
                "action": action,
                "rollback_from": rollback_from or None,
                "error": str(exc),
            }
        _save_state()
        duration = int((time.time() - started) * 1000)
        _push_history(action, False, str(exc), addons=addons, duration_ms=duration)
    finally:
        _install.in_progress = False


def _runtime_state_label(container: dict[str, Any]) -> str:
    if _install.in_progress:
        return "installing"
    if not container.get("exists"):
        return "not_installed"
    status = container.get("status")
    if status == "running":
        return "running"
    if status in {"created", "restarting", "paused"}:
        return status
    if status in {"exited", "dead"}:
        return "stopped"
    if status == "error":
        return "error"
    return "stopped"


def get_status(include_logs: bool = True) -> dict[str, Any]:
    state = _load_state()
    container = _inspect_container()
    runtime_logs = _read_runtime_logs(limit=120) if include_logs else []

    with _lock:
        system_logs = list(_logs)[-120:]

    return {
        "state": _runtime_state_label(container),
        "container": container,
        "install": {
            "in_progress": _install.in_progress,
            "progress": _install.progress,
            "step": _install.step,
            "error": _install.error,
            "started_at": _install.started_at,
            "finished_at": _install.finished_at,
            "build_id": _install.build_id,
        },
        "selected_addons": list(state.get("selected_addons") or []),
        "available_addons": AVAILABLE_ADDONS,
        "presets": PRESETS,
        "history": list(state.get("history") or [])[:20],
        "profiles": list(state.get("profiles") or [])[:20],
        "last_install": state.get("last_install"),
        "monitor": {
            "enabled": _monitor_thread is not None and _monitor_thread.is_alive(),
            "manual_stop": bool(state.get("manual_stop", False)),
            "auto_restart_count": int(state.get("auto_restart_count", 0)),
            "interval_sec": RUNTIME_MONITOR_INTERVAL,
        },
        "logs": {
            "system": system_logs,
            "runtime": runtime_logs,
        },
    }


def get_logs(source: str = "all", limit: int = 200, since_id: int = 0) -> dict[str, Any]:
    clean_source = str(source or "all").strip().lower()
    clean_limit = max(10, min(500, int(limit or 200)))
    clean_since = max(0, int(since_id or 0))

    with _lock:
        base = list(_logs)

    if clean_source != "all":
        base = [row for row in base if row.get("source") == clean_source]
    if clean_since:
        base = [row for row in base if int(row.get("id") or 0) > clean_since]

    rows = base[-clean_limit:]

    if clean_source in {"all", "runtime"}:
        runtime_logs = _read_runtime_logs(limit=clean_limit)
        if clean_source == "runtime":
            rows = runtime_logs
        else:
            rows = (rows + runtime_logs)[-clean_limit:]

    return {"entries": rows, "source": clean_source, "limit": clean_limit, "since_id": clean_since}


def start_install(addons: list[str], reinstall: bool = False, action: str = "", rollback_from: str = "") -> dict[str, Any]:
    global _install_thread
    clean_addons = _validate_addons(addons)
    action_name = action or ("reinstall" if reinstall else "install")
    next_build_id = _new_build_id()

    with _lock:
        if _install.in_progress or (_install_thread is not None and _install_thread.is_alive()):
            raise ServiceError(409, "Install is already running")

        _install.in_progress = True
        _install.progress = 2
        _install.step = "prepare"
        _install.error = ""
        _install.started_at = time.time()
        _install.finished_at = 0.0
        _install.build_id = next_build_id

    _install_thread = threading.Thread(target=_install_worker, args=(clean_addons, action_name, rollback_from), daemon=True)
    _install_thread.start()
    return {
        "status": "started",
        "addons": clean_addons,
        "reinstall": bool(reinstall),
        "action": action_name,
        "build_id": next_build_id,
        "rollback_from": rollback_from or None,
    }


def start_container() -> dict[str, Any]:
    if _install.in_progress:
        raise ServiceError(409, "Install is in progress")
    try:
        result = _create_or_start_container(recreate=False)
    except NotFound as exc:
        raise ServiceError(404, f"Container not found: {exc}")
    except APIError as exc:
        raise ServiceError(500, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(500, str(exc))

    with _lock:
        state = _load_state()
        state["manual_stop"] = False
        state["auto_restart_count"] = 0
    _save_state()
    _append_log("system", "Container started")
    _push_history("start", True, "Container started")
    return result


def apply_caddyfile() -> dict[str, Any]:
    if _install.in_progress:
        raise ServiceError(409, "Install is in progress")

    client = _docker_client()
    try:
        container = client.containers.get(RUNTIME_CONTAINER)
    except NotFound:
        return start_container()
    except APIError as exc:
        raise ServiceError(500, str(exc))

    try:
        container.reload()
        if str(getattr(container, "status", "") or "") != "running":
            container.start()
            container.reload()
        _sync_caddyfile_into_container(container)
        reload_result = container.exec_run(["caddy", "reload", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"])
    except APIError as exc:
        raise ServiceError(500, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(500, str(exc))

    exit_code = getattr(reload_result, "exit_code", None)
    output = getattr(reload_result, "output", None)
    if exit_code is None and isinstance(reload_result, tuple):
        exit_code = reload_result[0]
        output = reload_result[1] if len(reload_result) > 1 else b""

    code = int(exit_code or 0)
    if isinstance(output, (bytes, bytearray)):
        text = output.decode("utf-8", errors="ignore").strip()
    else:
        text = str(output or "").strip()

    if code != 0:
        detail = text or f"exit_code={code}"
        raise ServiceError(500, f"Caddy reload failed: {detail}")

    container.reload()
    _append_log("system", "Caddyfile synced and reloaded")
    return {
        "status": container.status,
        "container_name": RUNTIME_CONTAINER,
        "reload_output": text,
    }


def stop_container() -> dict[str, Any]:
    if _install.in_progress:
        raise ServiceError(409, "Install is in progress")

    client = _docker_client()
    try:
        container = client.containers.get(RUNTIME_CONTAINER)
    except NotFound:
        raise ServiceError(404, "Container not found")
    except APIError as exc:
        raise ServiceError(500, str(exc))

    try:
        container.stop(timeout=10)
        container.reload()
    except APIError as exc:
        raise ServiceError(500, str(exc))

    with _lock:
        state = _load_state()
        state["manual_stop"] = True
    _save_state()
    _append_log("system", "Container stopped")
    _push_history("stop", True, "Container stopped")

    return {
        "status": container.status,
        "container_name": RUNTIME_CONTAINER,
    }


def reconcile_on_startup() -> None:
    state = _load_state()
    try:
        container = _inspect_container()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to inspect Caddy runtime container on startup")
        return

    if not container.get("exists"):
        _append_log("monitor", "Startup: runtime container not found")
        start_monitor()
        return

    _append_log("monitor", f"Startup: found container status={container.get('status')}")
    if bool(state.get("manual_stop", False)):
        _append_log("monitor", "Startup: skip auto-start due to manual_stop flag")
        start_monitor()
        return
    if container.get("status") != "running":
        try:
            start_container()
            _append_log("monitor", "Startup: container auto-started")
        except ServiceError as exc:
            _append_log("monitor", f"Startup auto-start failed: {exc.detail}", level="error")
    start_monitor()


def rollback(target_build_id: str = "") -> dict[str, Any]:
    state = _load_state()
    profiles = list(state.get("profiles") or [])
    if not profiles:
        raise ServiceError(404, "No successful build profiles found")

    selected = list(state.get("selected_addons") or [])
    target = None
    if target_build_id:
        target = next((item for item in profiles if item.get("build_id") == target_build_id), None)
    else:
        target = next((item for item in profiles if list(item.get("addons") or []) != selected), None)
        if target is None:
            target = profiles[0]

    if not target:
        raise ServiceError(404, "Rollback target not found")

    addons = list(target.get("addons") or [])
    build_id = str(target.get("build_id") or "")
    return start_install(addons=addons, reinstall=True, action="rollback", rollback_from=build_id)


def stream_payload(source: str = "all", since_id: int = 0) -> dict[str, Any]:
    status = get_status(include_logs=False)
    logs = get_logs(source=source, limit=250, since_id=since_id)
    entries = logs.get("entries") or []
    next_id = since_id
    if entries:
        next_id = max(int(item.get("id") or 0) for item in entries)
    return {
        "status": status,
        "logs": entries,
        "next_since_id": next_id,
    }


def _monitor_loop() -> None:
    _append_log("monitor", "Watchdog started")
    while not _monitor_stop.wait(RUNTIME_MONITOR_INTERVAL):
        if _install.in_progress:
            continue
        try:
            container = _inspect_container()
        except Exception as exc:  # noqa: BLE001
            _append_log("monitor", f"Inspect failed: {exc}", level="error")
            continue

        if not container.get("exists"):
            continue

        status = str(container.get("status") or "")
        if status == "running":
            continue

        with _lock:
            state = _load_state()
            attempts = int(state.get("auto_restart_count", 0))
            manual_stop = bool(state.get("manual_stop", False))

        if manual_stop:
            continue

        if attempts >= RUNTIME_MAX_RESTARTS:
            _append_log("monitor", "Auto-restart limit reached", level="error")
            continue

        try:
            _append_log("monitor", f"Container status={status}; trying restart")
            start_container()
            with _lock:
                state = _load_state()
                state["auto_restart_count"] = int(state.get("auto_restart_count", 0)) + 1
            _save_state()
            _append_log("monitor", "Auto-restart success")
        except ServiceError as exc:
            _append_log("monitor", f"Auto-restart failed: {exc.detail}", level="error")


def start_monitor() -> None:
    global _monitor_thread
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    if _monitor_thread is not None and _monitor_thread.is_alive():
        return
    _monitor_stop.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()


def stop_monitor() -> None:
    _monitor_stop.set()
