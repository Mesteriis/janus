from __future__ import annotations

import secrets
from pathlib import Path

from . import settings

_cache = {"mtime": None, "value": ""}


def _read_token_file(path: Path) -> str:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return ""
    if _cache["mtime"] == stat.st_mtime:
        return _cache["value"]
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        value = ""
    _cache["mtime"] = stat.st_mtime
    _cache["value"] = value
    return value


def get_token() -> str:
    return _read_token_file(settings.MCP_TOKEN_FILE)


def set_token(value: str) -> None:
    path = settings.MCP_TOKEN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip(), encoding="utf-8")
    try:
        stat = path.stat()
    except OSError:
        _cache["mtime"] = None
        _cache["value"] = value.strip()
        return
    _cache["mtime"] = stat.st_mtime
    _cache["value"] = value.strip()


def clear_token() -> None:
    path = settings.MCP_TOKEN_FILE
    try:
        if path.exists():
            path.unlink()
    except OSError:
        try:
            path.write_text("", encoding="utf-8")
        except OSError:
            pass
    _cache["mtime"] = None
    _cache["value"] = ""


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def mcp_enabled() -> bool:
    return bool(get_token())


def verify_token(candidate: str | None) -> bool:
    if not candidate:
        return False
    return secrets.compare_digest(candidate, get_token())
