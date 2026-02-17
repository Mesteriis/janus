def test_misc_imports():
    import app.api
    import app.settings
    from app.plugins import default_plugins
    from app.cloudflare import constants, exception

    plugins = default_plugins()
    assert "tlsredis" in plugins
    assert constants.TOKEN_NAME
    assert exception.CloudflareError
