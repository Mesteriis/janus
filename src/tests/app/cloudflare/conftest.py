import pytest


@pytest.fixture()
def cf_env(monkeypatch, tmp_path, reload_settings):
    def _apply(**overrides):
        monkeypatch.setenv("CLOUDFLARE_STATE_FILE", str(tmp_path / "state.json"))
        monkeypatch.setenv("CLOUDFLARE_HOSTNAMES_FILE", str(tmp_path / "hostnames.json"))
        for key, value in overrides.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        reload_settings()
        return tmp_path

    return _apply
