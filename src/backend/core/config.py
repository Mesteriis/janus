from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_project_root() / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_root: Path = Field(default_factory=_project_root)

    routes_file: Path = Field(default_factory=lambda: _path("docker", "caddy", "routes.json"))
    caddy_config: Path = Field(default_factory=lambda: _path("docker", "caddy", "config.json5"))
    caddy_errors_dir: Path = Field(default_factory=lambda: _path("docker", "caddy", "errors"))
    caddy_email: str = "avm@sh-inc.ru"
    caddy_validate: bool = False
    caddy_bin: str = "caddy"
    dashboard_port: int = 8090

    auth_password_file: Path = Field(default_factory=lambda: _path("auth.txt"))
    auth_cookie_name: str = "janus_auth"

    tls_redis_address: str = ""
    tls_redis_db: int | None = None
    tls_redis_username: str = ""
    tls_redis_password: str = ""
    tls_redis_prefix: str = ""

    cloudflare_api_token: str = ""
    cloudflare_default_service: str = "http://caddy:80"
    cloudflare_hostnames_file: Path = Field(default_factory=lambda: _path("cloudflared", "hostnames.json"))
    cloudflare_tunnel_token: str = ""
    cloudflare_state_file: Path = Field(default_factory=lambda: _path("cloudflared", "state.json"))

    cf_tunnel_image: str = "cloudflare/cloudflared:latest"
    cf_tunnel_container: str = "tunel-cloudflared"
    cf_tunnel_network: str = "host"
    # Local dev default; docker-compose overrides to /cloudflared
    cf_tunnel_dir: str = str(_path("cloudflared"))

    @model_validator(mode="after")
    def _normalize_paths(self) -> "Settings":
        root = self.project_root
        if not root.is_absolute():
            root = _project_root() / root
        self.project_root = root

        self.routes_file = _resolve_path(root, self.routes_file)
        self.caddy_config = _resolve_path(root, self.caddy_config)
        self.caddy_errors_dir = _resolve_path(root, self.caddy_errors_dir)
        self.auth_password_file = _resolve_path(root, self.auth_password_file)
        self.cloudflare_hostnames_file = _resolve_path(root, self.cloudflare_hostnames_file)
        self.cloudflare_state_file = _resolve_path(root, self.cloudflare_state_file)

        if self.cf_tunnel_dir:
            p = Path(self.cf_tunnel_dir)
            if not p.is_absolute():
                p = root / p
            self.cf_tunnel_dir = str(p)

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
