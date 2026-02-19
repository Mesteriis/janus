import re
from pathlib import Path

from .core import get_settings

_settings = get_settings()

PROJECT_ROOT = _settings.project_root
ROUTES_FILE = _settings.routes_file
CADDY_CONFIG = _settings.caddy_config
CADDYFILE_PATH = _settings.caddyfile_path
CADDY_ERRORS_DIR = _settings.caddy_errors_dir
CADDY_EMAIL = _settings.caddy_email
CADDY_VALIDATE = _settings.caddy_validate
CADDY_BIN = _settings.caddy_bin
DASHBOARD_PORT = _settings.dashboard_port
SETTINGS_JSON_FILE = _settings.settings_json_file
AUTH_PASSWORD_FILE = _settings.auth_password_file
AUTH_COOKIE_NAME = _settings.auth_cookie_name
MCP_TOKEN_FILE = _settings.mcp_token_file
TLS_REDIS_ADDRESS = _settings.tls_redis_address
TLS_REDIS_DB = _settings.tls_redis_db
TLS_REDIS_USERNAME = _settings.tls_redis_username
TLS_REDIS_PASSWORD = _settings.tls_redis_password
TLS_REDIS_PREFIX = _settings.tls_redis_prefix
CLOUDFLARE_API_TOKEN = _settings.cloudflare_api_token
CLOUDFLARE_API_TOKEN_FILE = _settings.cloudflare_api_token_file
CLOUDFLARE_DEFAULT_SERVICE = _settings.cloudflare_default_service
CLOUDFLARE_HOSTNAMES_FILE = _settings.cloudflare_hostnames_file
CLOUDFLARE_TUNNEL_TOKEN = _settings.cloudflare_tunnel_token
CF_STATE_FILE = _settings.cloudflare_state_file
FEATURE_TUNNEL_ENABLED = _settings.feature_tunnel_enabled
FEATURE_VPN_ENABLED = _settings.feature_vpn_enabled
CF_TUNNEL_IMAGE = _settings.cf_tunnel_image
CF_TUNNEL_CONTAINER = _settings.cf_tunnel_container
CF_TUNNEL_NETWORK = _settings.cf_tunnel_network
CF_TUNNEL_DIR = _settings.cf_tunnel_dir
VPN_DATA_DIR = _settings.vpn_data_dir
VPN_STATE_FILE = _settings.vpn_state_file
VPN_WG_IMAGE = _settings.vpn_wg_image
VPN_CONTAINER_PREFIX = _settings.vpn_container_prefix
VPN_PORT_BASE = _settings.vpn_port_base
VPN_SUBNET_BASE = _settings.vpn_subnet_base
VPN_PUBLIC_ENDPOINT = _settings.vpn_public_endpoint

DOMAIN_RE = re.compile(r"^(\*\.)?([a-zA-Z0-9-]+\.)+[A-Za-z]{2,63}$")
METHOD_RE = re.compile(r"^[A-Z]+$")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
