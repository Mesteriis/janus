import types

import pytest


def test_docker_ctl_start_stop_status(monkeypatch):
    from app import docker_ctl

    class DummyContainer:
        def __init__(self):
            self.status = "running"
            self.id = "cid"

        def stop(self, timeout=5):
            self.status = "stopped"

        def remove(self):
            self.status = "removed"

        def reload(self):
            return None

        def logs(self, tail=20):
            return b"log"

    class DummyContainers:
        def __init__(self):
            self._current = DummyContainer()
            self.raise_not_found = False
            self.raise_api = False

        def get(self, name):
            if self.raise_api:
                raise docker_ctl.APIError("boom")
            if self.raise_not_found:
                raise docker_ctl.NotFound()
            return self._current

        def run(self, *args, **kwargs):
            self._current = DummyContainer()
            return self._current

    class DummyImages:
        def pull(self, image):
            return None

    class DummyClient:
        def __init__(self):
            self.containers = DummyContainers()
            self.images = DummyImages()

    dummy = DummyClient()
    monkeypatch.setattr(docker_ctl, "_client", lambda: dummy)

    # start with existing container
    res = docker_ctl.start_tunnel("tok")
    assert res["id"] == "cid"

    # stop
    stop = docker_ctl.stop_tunnel()
    assert stop["status"] == "stopped"

    # status running
    status = docker_ctl.tunnel_status()
    assert status["status"] in ("running", "removed", "stopped")

    # not found
    dummy.containers.raise_not_found = True
    assert docker_ctl.stop_tunnel()["status"] == "not_found"
    assert docker_ctl.tunnel_status()["status"] == "not_found"

    # start when no existing container
    res2 = docker_ctl.start_tunnel("tok")
    assert res2["id"] == "cid"

    # api error
    dummy.containers.raise_not_found = False
    dummy.containers.raise_api = True
    assert docker_ctl.tunnel_status()["status"] == "error"


def test_docker_ctl_start_requires_token(monkeypatch, reload_settings):
    from app import docker_ctl

    monkeypatch.setenv("CLOUDFLARE_TUNNEL_TOKEN", "")
    reload_settings()

    with pytest.raises(ValueError):
        docker_ctl.start_tunnel("")


def test_docker_ctl_client():
    from app import docker_ctl

    assert docker_ctl._client() is not None
