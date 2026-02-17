import importlib

import pytest


@pytest.fixture()
def reload_settings():
    def _reload():
        import app.core.config as cfg
        import app.settings as settings

        cfg.get_settings.cache_clear()
        importlib.reload(settings)
        return settings

    return _reload
