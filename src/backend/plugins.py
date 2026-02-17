from . import settings

def default_plugins() -> dict:
    return {
        "tlsredis": {
            "address": settings.TLS_REDIS_ADDRESS or "",
            "db": settings.TLS_REDIS_DB,
            "username": settings.TLS_REDIS_USERNAME or None,
            "password": settings.TLS_REDIS_PASSWORD or None,
            "key_prefix": settings.TLS_REDIS_PREFIX or None,
        },
        "realip": {"presets": ["cloudflare"], "cidrs": []},
        "prometheus": {"enabled": False, "path": "/metrics"},
        "trace": {"enabled": False, "exporter": {"otlp_endpoint": "", "headers": {}}},
        "geoip": {"enabled": False, "action": "block", "countries": [], "asn": []},
        "crowdsec": {"enabled": False, "lapi_url": "", "api_key": "", "fallback_action": "allow"},
        "security": {"portal_name": "secure", "issuers": [], "jwt": {}},
        "appsec": {"enabled": False, "policy": "owasp"},
        "cache": {"engine": "souin", "ttl": "120s", "excluded_paths": [], "key_strategy": "path"},
        "docker_proxy": {"enabled": False, "labels_filter": ""},
        "s3storage": {"enabled": False, "bucket": "", "region": "", "endpoint": "", "access_key": "", "secret_key": ""},
        "fs_s3": {"enabled": False, "bucket": "", "region": "", "endpoint": "", "access_key": "", "secret_key": "", "root": "/", "browse": False},
    }
