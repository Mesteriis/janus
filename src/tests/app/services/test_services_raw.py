import json

import pytest


@pytest.mark.asyncio
async def test_update_routes_raw(monkeypatch, tmp_path, reload_settings):
    from app.services import raw as raw_service
    from app.services import provisioning

    monkeypatch.setenv("ROUTES_FILE", str(tmp_path / "routes.json"))
    monkeypatch.setenv("CADDY_CONFIG", str(tmp_path / "config.json5"))
    reload_settings()

    calls = {"trigger": None}

    async def _prov(data, trigger):
        calls["trigger"] = trigger
        return {"status": "ok"}

    monkeypatch.setattr(raw_service, "provision_after_routes_change", _prov)

    payload = {"routes": []}
    res = await raw_service.update_routes_raw(json.dumps(payload))
    assert res["status"] == "saved"
    assert calls["trigger"] == provisioning.TRIGGER_RAW
