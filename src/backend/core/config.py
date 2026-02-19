from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _path(*parts: str) -> Path:
    return _project_root().joinpath(*parts)


def _resolve_path(root: Path, value: Path | str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _resolve_root(value: Path | str | None) -> Path:
    root = Path(value) if value else _project_root()
    if not root.is_absolute():
        root = _project_root() / root
    return root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_project_root() / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_root: Path = Field(default_factory=_project_root)

    routes_file: Path = Field(default_factory=lambda: _path("data", "caddy", "routes.json"))
    caddyfile_path: Path = Field(default_factory=lambda: _path("data", "caddy", "Caddyfile"))
    caddy_config: Path = Field(default_factory=lambda: _path("data", "caddy", "config.json5"))
    caddy_errors_dir: Path = Field(default_factory=lambda: _path("docker", "caddy", "errors"))
    caddy_email: str = "avm@sh-inc.ru"
    caddy_validate: bool = False
    caddy_bin: str = "caddy"
    dashboard_port: int = 8090
    settings_json_file: Path = Field(default_factory=lambda: _path("data", "settings", "app_settings.json"))

    auth_password_file: Path = Field(default_factory=lambda: _path("auth.txt"))
    auth_cookie_name: str = "janus_auth"
    mcp_token_file: Path = Field(default_factory=lambda: _path("data", "mcp", "token.txt"))

    tls_redis_address: str = ""
    tls_redis_db: int | None = None
    tls_redis_username: str = ""
    tls_redis_password: str = ""
    tls_redis_prefix: str = ""

    cloudflare_api_token: str = ""
    cloudflare_api_token_file: Path = Field(default_factory=lambda: _path("data", "cloudflare", "api_token.txt"))
    cloudflare_default_service: str = "http://127.0.0.1:80"
    cloudflare_hostnames_file: Path = Field(default_factory=lambda: _path("data", "cloudflare", "hostnames.json"))
    cloudflare_tunnel_token: str = ""
    cloudflare_state_file: Path = Field(default_factory=lambda: _path("data", "cloudflare", "state.json"))
    feature_tunnel_enabled: bool = True
    feature_vpn_enabled: bool = True

    cf_tunnel_image: str = "cloudflare/cloudflared:latest"
    cf_tunnel_container: str = "janus-cloudflared"
    cf_tunnel_network: str = "host"
    cf_tunnel_dir: str = str(_path("data", "cloudflare"))

    vpn_data_dir: Path = Field(default_factory=lambda: _path("data", "vpn"))
    vpn_state_file: Path = Field(default_factory=lambda: _path("data", "vpn", "state.json"))
    vpn_wg_image: str = "ghcr.io/linuxserver/wireguard:latest"
    vpn_container_prefix: str = "janus-wg"
    vpn_port_base: int = 51820
    vpn_subnet_base: str = "10.66"
    vpn_public_endpoint: str = ""

    @model_validator(mode="before")
    @classmethod
    def _merge_from_settings_file(cls, data: Any) -> Any:
        values = dict(data or {}) if isinstance(data, dict) else {}
        root = _resolve_root(values.get("project_root"))
        raw_path = values.get("settings_json_file")
        settings_path = Path(raw_path) if raw_path else root / "data" / "settings" / "app_settings.json"
        if not settings_path.is_absolute():
            settings_path = root / settings_path
        values["settings_json_file"] = str(settings_path)

        try:
            if settings_path.exists():
                payload = json.loads(settings_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    for key, value in payload.items():
                        if key in cls.model_fields:
                            values[key] = value
        except Exception:
            # Invalid runtime settings file should not break startup.
            return values
        return values

    @model_validator(mode="after")
    def _normalize_paths(self) -> "Settings":
        root = self.project_root
        if not root.is_absolute():
            root = _project_root() / root
        self.project_root = root

        self.routes_file = _resolve_path(root, self.routes_file)
        self.caddyfile_path = _resolve_path(root, self.caddyfile_path)
        self.caddy_config = _resolve_path(root, self.caddy_config)
        self.caddy_errors_dir = _resolve_path(root, self.caddy_errors_dir)
        self.auth_password_file = _resolve_path(root, self.auth_password_file)
        self.mcp_token_file = _resolve_path(root, self.mcp_token_file)
        self.settings_json_file = _resolve_path(root, self.settings_json_file)
        self.cloudflare_hostnames_file = _resolve_path(root, self.cloudflare_hostnames_file)
        self.cloudflare_api_token_file = _resolve_path(root, self.cloudflare_api_token_file)
        self.cloudflare_state_file = _resolve_path(root, self.cloudflare_state_file)
        self.vpn_data_dir = _resolve_path(root, self.vpn_data_dir)
        self.vpn_state_file = _resolve_path(root, self.vpn_state_file)

        if self.cf_tunnel_dir:
            p = Path(self.cf_tunnel_dir)
            if not p.is_absolute():
                p = root / p
            self.cf_tunnel_dir = str(p)

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
