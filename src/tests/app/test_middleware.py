import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.middleware import CorrelationIdMiddleware


def test_correlation_id_header_and_logs(client_factory, capsys):
    client, _ = client_factory()

    resp = client.get("/", headers={"X-Correlation-Id": "cid-123"})
    assert resp.headers.get("X-Correlation-Id") == "cid-123"

    captured = capsys.readouterr().err
    assert "request.start" in captured
    assert "\"correlation_id\": \"cid-123\"" in captured


def test_correlation_id_middleware_error_log(capsys):
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=True)
    with pytest.raises(RuntimeError):
        client.get("/boom")

    captured = capsys.readouterr().err
    assert "request.error" in captured
