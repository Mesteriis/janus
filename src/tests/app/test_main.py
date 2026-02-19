import importlib

from fastapi.testclient import TestClient


def test_index_returns_503_when_missing(client_factory, monkeypatch, tmp_path):
    client, _ = client_factory()

    import backend.settings as settings
    importlib.reload(settings)

    empty_base = tmp_path / "base"
    (empty_base / "templates").mkdir(parents=True, exist_ok=True)
    empty_static = tmp_path / "static"
    empty_static.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "BASE_DIR", empty_base)
    monkeypatch.setattr(settings, "STATIC_DIR", empty_static)

    import backend.main as main

    importlib.reload(main)
    test_client = TestClient(main.create_app())

    resp = test_client.get("/")
    assert resp.status_code == 503


def test_index_serves_file_when_exists(client_factory, monkeypatch, tmp_path):
    client, _ = client_factory()

    index_dir = tmp_path / "static"
    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / "index.html"
    index_path.write_text("<html>ok</html>")

    import backend.settings as settings
    importlib.reload(settings)
    monkeypatch.setattr(settings, "STATIC_DIR", index_dir)

    import backend.main as main

    importlib.reload(main)
    app = main.create_app()
    test_client = TestClient(app)

    resp = test_client.get("/")
    assert resp.status_code == 200
