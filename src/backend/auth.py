from __future__ import annotations

import hmac
import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import settings

_cache = {"mtime": None, "value": ""}
_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 390_000
_SESSION_TTL_SECONDS = 24 * 60 * 60
_sessions_lock = threading.RLock()


@dataclass
class _Session:
    token: str
    expires_at: float


_sessions: dict[str, _Session] = {}


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


def _hash_password(value: str, *, iterations: int = _PASSWORD_ITERATIONS, salt: str | None = None) -> str:
    clean = value.strip()
    salt_hex = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        clean.encode("utf-8"),
        salt_hex.encode("utf-8"),
        iterations,
    ).hex()
    return f"{_PASSWORD_SCHEME}${iterations}${salt_hex}${digest}"


def _verify_password(candidate: str, stored: str) -> bool:
    if not stored:
        return False
    clean_candidate = candidate.strip()
    # Backward compatibility for legacy plaintext values.
    if not stored.startswith(f"{_PASSWORD_SCHEME}$"):
        return hmac.compare_digest(clean_candidate, stored)
    try:
        _, iterations_raw, salt_hex, _digest_hex = stored.split("$", 3)
        iterations = int(iterations_raw)
    except (TypeError, ValueError):
        return False
    calculated = _hash_password(clean_candidate, iterations=iterations, salt=salt_hex)
    return hmac.compare_digest(calculated, stored)


def _prune_sessions(now: float | None = None) -> None:
    ts = now or time.time()
    expired = [token for token, session in _sessions.items() if session.expires_at <= ts]
    for token in expired:
        _sessions.pop(token, None)


def clear_sessions() -> None:
    with _sessions_lock:
        _sessions.clear()


def get_password() -> str:
    return _read_password_file(settings.AUTH_PASSWORD_FILE)


def set_password(value: str | None) -> None:
    path = settings.AUTH_PASSWORD_FILE
    if value:
        hashed = _hash_password(value)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(hashed, encoding="utf-8")
        try:
            stat = path.stat()
        except OSError:
            _cache["mtime"] = None
            _cache["value"] = hashed
            clear_sessions()
            return
        _cache["mtime"] = stat.st_mtime
        _cache["value"] = hashed
        clear_sessions()
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
    clear_sessions()


def auth_enabled() -> bool:
    return bool(get_password())


def check_password(candidate: str | None) -> bool:
    if not candidate:
        return False
    return _verify_password(candidate, get_password())


def issue_session_token() -> str:
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + _SESSION_TTL_SECONDS
    session = _Session(token=token, expires_at=expires_at)
    with _sessions_lock:
        _prune_sessions()
        _sessions[token] = session
    return token


def is_session_token_valid(token: str | None) -> bool:
    if not token:
        return False
    with _sessions_lock:
        _prune_sessions()
        session = _sessions.get(token)
        if session is None:
            return False
        if session.expires_at <= time.time():
            _sessions.pop(token, None)
            return False
        return True


def revoke_session_token(token: str | None) -> None:
    if not token:
        return
    with _sessions_lock:
        _sessions.pop(token, None)
