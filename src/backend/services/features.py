from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from .. import settings
from ..core import get_settings

_FEATURE_TUNNEL_KEY = "feature_tunnel_enabled"
_FEATURE_VPN_KEY = "feature_vpn_enabled"
_LOCK = Lock()


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


def _settings_file() -> Path:
    return Path(settings.SETTINGS_JSON_FILE)


def _default_settings_payload() -> dict:
    payload = get_settings().model_dump(mode="json")
    payload[_FEATURE_TUNNEL_KEY] = _to_bool(
        payload.get(_FEATURE_TUNNEL_KEY),
        bool(settings.FEATURE_TUNNEL_ENABLED),
    )
    payload[_FEATURE_VPN_KEY] = _to_bool(
        payload.get(_FEATURE_VPN_KEY),
        bool(settings.FEATURE_VPN_ENABLED),
    )
    return payload


def _features_payload(payload: dict[str, Any]) -> dict:
    tunnel_enabled = _to_bool(payload.get(_FEATURE_TUNNEL_KEY), bool(settings.FEATURE_TUNNEL_ENABLED))
    vpn_enabled = _to_bool(payload.get(_FEATURE_VPN_KEY), bool(settings.FEATURE_VPN_ENABLED))
    return {
        "tunnel_enabled": tunnel_enabled,
        "vpn_enabled": vpn_enabled,
        "inbound_enabled": tunnel_enabled or vpn_enabled,
    }


def _save_settings_payload(payload: dict[str, Any]) -> None:
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_settings_payload() -> dict:
    defaults = _default_settings_payload()
    path = _settings_file()
    if not path.exists():
        _save_settings_payload(defaults)
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}

    merged = dict(defaults)
    merged.update(raw)
    merged[_FEATURE_TUNNEL_KEY] = _to_bool(merged.get(_FEATURE_TUNNEL_KEY), bool(settings.FEATURE_TUNNEL_ENABLED))
    merged[_FEATURE_VPN_KEY] = _to_bool(merged.get(_FEATURE_VPN_KEY), bool(settings.FEATURE_VPN_ENABLED))

    if merged != raw:
        _save_settings_payload(merged)
    return merged


def ensure_runtime_settings_file() -> dict:
    with _LOCK:
        payload = _load_settings_payload()
    return {
        "file": str(_settings_file()),
        "features": _features_payload(payload),
    }


def get_runtime_settings() -> dict:
    payload = _load_settings_payload()
    return {
        "file": str(_settings_file()),
        "settings": payload,
        "features": _features_payload(payload),
    }


def get_features() -> dict:
    return _features_payload(_load_settings_payload())


def is_tunnel_enabled() -> bool:
    return bool(get_features()["tunnel_enabled"])


def is_vpn_enabled() -> bool:
    return bool(get_features()["vpn_enabled"])


def update_features(payload: dict | None) -> dict:
    data = payload or {}
    with _LOCK:
        settings_payload = _load_settings_payload()
        if "tunnel_enabled" in data or _FEATURE_TUNNEL_KEY in data:
            value = data.get("tunnel_enabled", data.get(_FEATURE_TUNNEL_KEY))
            settings_payload[_FEATURE_TUNNEL_KEY] = _to_bool(
                value,
                bool(settings_payload.get(_FEATURE_TUNNEL_KEY, settings.FEATURE_TUNNEL_ENABLED)),
            )
        if "vpn_enabled" in data or _FEATURE_VPN_KEY in data:
            value = data.get("vpn_enabled", data.get(_FEATURE_VPN_KEY))
            settings_payload[_FEATURE_VPN_KEY] = _to_bool(
                value,
                bool(settings_payload.get(_FEATURE_VPN_KEY, settings.FEATURE_VPN_ENABLED)),
            )
        _save_settings_payload(settings_payload)
        return {
            "file": str(_settings_file()),
            **_features_payload(settings_payload),
        }
