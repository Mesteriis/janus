import re
from pathlib import Path

from .core import get_settings

_settings = get_settings()

PROJECT_ROOT = _settings.project_root
ROUTES_FILE = _settings.routes_file
CADDY_CONFIG = _settings.caddy_config
CADDY_ERRORS_DIR = _settings.caddy_errors_dir
CADDY_EMAIL = _settings.caddy_email
CADDY_VALIDATE = _settings.caddy_validate
CADDY_BIN = _settings.caddy_bin
DASHBOARD_PORT = _settings.dashboard_port
AUTH_PASSWORD_FILE = _settings.auth_password_file
AUTH_COOKIE_NAME = _settings.auth_cookie_name
TLS_REDIS_ADDRESS = _settings.tls_redis_address
TLS_REDIS_DB = _settings.tls_redis_db
TLS_REDIS_USERNAME = _settings.tls_redis_username
TLS_REDIS_PASSWORD = _settings.tls_redis_password
TLS_REDIS_PREFIX = _settings.tls_redis_prefix
CLOUDFLARE_API_TOKEN = _settings.cloudflare_api_token
CLOUDFLARE_DEFAULT_SERVICE = _settings.cloudflare_default_service
CLOUDFLARE_HOSTNAMES_FILE = _settings.cloudflare_hostnames_file
CLOUDFLARE_TUNNEL_TOKEN = _settings.cloudflare_tunnel_token
CF_STATE_FILE = _settings.cloudflare_state_file
CF_TUNNEL_IMAGE = _settings.cf_tunnel_image
CF_TUNNEL_CONTAINER = _settings.cf_tunnel_container
CF_TUNNEL_NETWORK = _settings.cf_tunnel_network
CF_TUNNEL_DIR = _settings.cf_tunnel_dir

DOMAIN_RE = re.compile(r"^(\*\.)?([a-zA-Z0-9-]+\.)+[A-Za-z]{2,63}$")
METHOD_RE = re.compile(r"^[A-Z]+$")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
