def test_misc_imports():
    import backend.api
    import backend.settings
    from backend.plugins import default_plugins
    from backend.cloudflare import constants, exception

    plugins = default_plugins()
    assert "tlsredis" in plugins
    assert constants.TOKEN_NAME
    assert exception.CloudflareError
