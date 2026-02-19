import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


def _clear_backend_modules():
    for name in list(sys.modules):
        if name == "backend" or name.startswith("backend."):
            del sys.modules[name]


@pytest.fixture()
def client_factory(monkeypatch, tmp_path):
    def _make(**env_overrides):
        _clear_backend_modules()

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

        import backend.core.lifespan as lifespan

        async def _noop():
            return None

        lifespan.sync_cloudflare_on_startup = _noop

        import backend.services.provisioning as provisioning

        def _noop_validate():
            return None

        async def _noop_sync(_data=None):
            return {"status": "ok"}

        monkeypatch.setattr(provisioning, "_run_caddy_validate", _noop_validate, raising=False)
        monkeypatch.setattr(provisioning, "ensure_tunnel_running", lambda: {"status": "running"}, raising=False)
        monkeypatch.setattr(provisioning, "sync_cloudflare_from_routes", _noop_sync, raising=False)

        import backend.main

        importlib.reload(backend.main)
        return TestClient(backend.main.app), tmp_path

    return _make
