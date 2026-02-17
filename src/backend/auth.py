from __future__ import annotations

from pathlib import Path

from . import settings

_cache = {"mtime": None, "value": ""}


def _read_password_file(path: Path) -> str:
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


def get_password() -> str:
    return _read_password_file(settings.AUTH_PASSWORD_FILE)


def set_password(value: str | None) -> None:
    path = settings.AUTH_PASSWORD_FILE
    if value:
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
        return

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


def auth_enabled() -> bool:
    return bool(get_password())


def check_password(candidate: str | None) -> bool:
    if not candidate:
        return False
    return candidate == get_password()
