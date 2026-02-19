from types import SimpleNamespace


def test_stream_payload_uses_since_id(monkeypatch):
    from backend.services import caddy_runtime as svc

    monkeypatch.setattr(svc, "get_status", lambda include_logs=False: {"state": "running"})
    monkeypatch.setattr(
        svc,
        "get_logs",
        lambda source="all", limit=250, since_id=0: {
            "entries": [
                {"id": since_id + 1, "source": source, "message": "line1"},
                {"id": since_id + 2, "source": source, "message": "line2"},
            ]
        },
    )

    payload = svc.stream_payload(source="build", since_id=10)
    assert payload["status"]["state"] == "running"
    assert len(payload["logs"]) == 2
    assert payload["next_since_id"] == 12


def test_rollback_allows_empty_profile(monkeypatch):
    from backend.services import caddy_runtime as svc

    monkeypatch.setattr(
        svc,
        "_load_state",
        lambda: {
            "profiles": [{"build_id": "b1", "addons": []}],
            "selected_addons": [],
        },
    )

    captured = {}

    def fake_start_install(addons, reinstall=False, action="", rollback_from=""):
        captured["addons"] = addons
        captured["reinstall"] = reinstall
        captured["action"] = action
        captured["rollback_from"] = rollback_from
        return {"status": "started"}

    monkeypatch.setattr(svc, "start_install", fake_start_install)

    result = svc.rollback()
    assert result["status"] == "started"
    assert captured["addons"] == []
    assert captured["reinstall"] is True
    assert captured["action"] == "rollback"
    assert captured["rollback_from"] == "b1"


def test_reconcile_skips_autostart_when_manual_stop(monkeypatch):
    from backend.services import caddy_runtime as svc

    monkeypatch.setattr(
        svc,
        "_load_state",
        lambda: {
            "manual_stop": True,
            "profiles": [],
            "selected_addons": [],
            "history": [],
            "auto_restart_count": 0,
            "last_install": None,
        },
    )
    monkeypatch.setattr(svc, "_inspect_container", lambda: {"exists": True, "status": "exited"})

    start_called = {"value": False}

    def fake_start_container():
        start_called["value"] = True
        return {"status": "running"}

    monkeypatch.setattr(svc, "start_container", fake_start_container)
    monkeypatch.setattr(svc, "start_monitor", lambda: None)
    monkeypatch.setattr(svc, "_append_log", lambda *args, **kwargs: None)

    svc.reconcile_on_startup()

    assert start_called["value"] is False
