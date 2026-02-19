import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_app_compat_aliases():
    """Legacy test compatibility: map old `app.*` imports to `backend.*`."""
    import types

    mapping = {
        "app": "backend",
        "app.api": "backend.api",
        "app.auth": "backend.auth",
        "app.caddy": "backend.caddy",
        "app.caddyfile": "backend.caddyfile",
        "app.cloudflare": "backend.cloudflare",
        "app.cloudflare.checker": "backend.cloudflare.checker",
        "app.cloudflare.client": "backend.cloudflare.client",
        "app.cloudflare.constants": "backend.cloudflare.constants",
        "app.cloudflare.exception": "backend.cloudflare.exception",
        "app.cloudflare.flow": "backend.cloudflare.flow",
        "app.cloudflare.hostnames": "backend.cloudflare.hostnames",
        "app.cloudflare.sdk": "backend.cloudflare.sdk",
        "app.cloudflare.store": "backend.cloudflare.store",
        "app.core": "backend.core",
        "app.core.config": "backend.core.config",
        "app.core.context": "backend.core.context",
        "app.core.lifespan": "backend.core.lifespan",
        "app.core.logging": "backend.core.logging",
        "app.core.middleware": "backend.core.middleware",
        "app.docker_ctl": "backend.docker_ctl",
        "app.main": "backend.main",
        "app.plugins": "backend.plugins",
        "app.services": "backend.services",
        "app.services.cloudflare": "backend.services.cloudflare",
        "app.services.errors": "backend.services.errors",
        "app.services.l4": "backend.services.l4",
        "app.services.plugins": "backend.services.plugins",
        "app.services.provisioning": "backend.services.provisioning",
        "app.services.raw": "backend.services.raw",
        "app.services.routes": "backend.services.routes",
        "app.services.tunnel": "backend.services.tunnel",
        "app.settings": "backend.settings",
        "app.storage": "backend.storage",
        "app.utils": "backend.utils",
        "app.validation": "backend.validation",
    }

    for legacy_name, backend_name in mapping.items():
        module = importlib.import_module(backend_name)
        sys.modules[legacy_name] = module

    # Keep package markers explicit for importlib/reload operations in tests.
    for package_name in ("app", "app.core", "app.services", "app.cloudflare"):
        module = sys.modules.get(package_name)
        if module and not hasattr(module, "__path__"):
            shim = types.ModuleType(package_name)
            shim.__dict__.update(module.__dict__)
            shim.__path__ = []  # type: ignore[attr-defined]
            sys.modules[package_name] = shim


_install_app_compat_aliases()


# Lightweight stub for docker package so imports succeed without docker-py installed.
if "docker" not in sys.modules:
    import types

    class NotFound(Exception):
        pass

    class APIError(Exception):
        pass

    class _DummyContainer:
        def __init__(self, status="running"):
            self.status = status
            self.id = "dummy"

        def stop(self, timeout=5):
            self.status = "exited"

        def remove(self):
            self.status = "removed"

        def logs(self, tail=20):
            return b""

        def reload(self):
            return None

    class _DummyContainers:
        def __init__(self):
            self._current = None

        def get(self, name):
            if self._current is None:
                raise NotFound()
            return self._current

        def run(
            self,
            image,
            command=None,
            name=None,
            detach=True,
            restart_policy=None,
            network_mode=None,
            volumes=None,
            environment=None,
        ):
            self._current = _DummyContainer()
            return self._current

    class _DummyAPI:
        def remove_container(self, name, force=False):
            return None

    class _DummyClient:
        def __init__(self):
            self.containers = _DummyContainers()
            self.images = self
            self.api = _DummyAPI()

        def pull(self, image):
            return None

    docker_errors = types.SimpleNamespace(NotFound=NotFound, APIError=APIError)
    sys.modules["docker"] = types.SimpleNamespace(from_env=lambda: _DummyClient(), errors=docker_errors)
    sys.modules["docker.errors"] = docker_errors


def _clear_app_modules():
    for name in list(sys.modules):
        if name == "backend" or name.startswith("backend.") or name == "app" or name.startswith("app."):
            del sys.modules[name]


@pytest.fixture()
def client_factory(monkeypatch, tmp_path):
    def _make(**env_overrides):
        _clear_app_modules()

        monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
        monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
        monkeypatch.setenv("SETTINGS_JSON_FILE", str(tmp_path / "app_settings.json"))
        monkeypatch.setenv("CLOUDFLARE_HOSTNAMES_FILE", str(tmp_path / "hostnames.json"))
        monkeypatch.setenv("CLOUDFLARE_STATE_FILE", str(tmp_path / "state.json"))
        monkeypatch.setenv("CADDY_EMAIL", "test@example.com")
        monkeypatch.setenv("CLOUDFLARE_DEFAULT_SERVICE", "http://127.0.0.1:8080")
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
        monkeypatch.setenv("AUTH_PASSWORD_FILE", str(tmp_path / "auth.txt"))

        for key, val in env_overrides.items():
            if val is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, val)

        import backend.core.config as cfg

        cfg.get_settings.cache_clear()
        _install_app_compat_aliases()

        import app.core.lifespan as lifespan

        async def _noop():
            return None

        lifespan.sync_cloudflare_on_startup = _noop

        import app.services.provisioning as provisioning

        def _noop_validate():
            return None

        async def _noop_sync(_data=None):
            return {"status": "ok"}

        monkeypatch.setattr(provisioning, "_run_caddy_validate", _noop_validate, raising=False)
        monkeypatch.setattr(provisioning, "ensure_tunnel_running", lambda: {"status": "running"}, raising=False)
        monkeypatch.setattr(provisioning, "sync_cloudflare_from_routes", _noop_sync, raising=False)

        import app.main

        importlib.reload(app.main)
        return TestClient(app.main.app), tmp_path

    return _make
