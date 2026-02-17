import pytest


def test_tunnel_start_missing_token(monkeypatch, reload_settings):
    from app.services import tunnel as tunnel_service

    monkeypatch.setenv("CLOUDFLARE_TUNNEL_TOKEN", "")
    reload_settings()
    with pytest.raises(tunnel_service.ServiceError):
        tunnel_service.start(None)


def test_tunnel_start_errors(monkeypatch, reload_settings):
    from app.services import tunnel as tunnel_service

    monkeypatch.setenv("CLOUDFLARE_TUNNEL_TOKEN", "tok")
    reload_settings()

    def bad_start(_token=None):
        raise ValueError("bad")

    monkeypatch.setattr(tunnel_service, "start_tunnel", bad_start)
    with pytest.raises(tunnel_service.ServiceError):
        tunnel_service.start("tok")

    def boom(_token=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(tunnel_service, "start_tunnel", boom)
    with pytest.raises(tunnel_service.ServiceError):
        tunnel_service.start("tok")


def test_tunnel_status_and_stop(monkeypatch):
    from app.services import tunnel as tunnel_service

    monkeypatch.setattr(tunnel_service, "tunnel_status", lambda: {"status": "running"})
    assert tunnel_service.status()["status"] == "running"

    monkeypatch.setattr(tunnel_service, "stop_tunnel", lambda: {"status": "stopped"})
    assert tunnel_service.stop()["status"] == "stopped"

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(tunnel_service, "tunnel_status", boom)
    with pytest.raises(tunnel_service.ServiceError):
        tunnel_service.status()

    monkeypatch.setattr(tunnel_service, "stop_tunnel", boom)
    with pytest.raises(tunnel_service.ServiceError):
        tunnel_service.stop()


def test_tunnel_ensure_running(monkeypatch, reload_settings):
    from app.services import tunnel as tunnel_service

    monkeypatch.setenv("CLOUDFLARE_TUNNEL_TOKEN", "tok")
    reload_settings()

    monkeypatch.setattr(tunnel_service, "tunnel_status", lambda: {"status": "running"})
    assert tunnel_service.ensure_running()["status"] == "running"

    monkeypatch.setattr(tunnel_service, "tunnel_status", lambda: {"status": "not_found"})
    monkeypatch.setattr(tunnel_service, "start_tunnel", lambda _token=None: {"status": "running"})
    assert tunnel_service.ensure_running()["status"] == "running"

    # missing token
    monkeypatch.setenv("CLOUDFLARE_TUNNEL_TOKEN", "")
    reload_settings()
    with pytest.raises(tunnel_service.ServiceError):
        tunnel_service.ensure_running()
