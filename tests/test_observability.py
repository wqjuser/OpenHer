"""HTTP observability middleware tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def build_test_client(monkeypatch) -> TestClient:
    monkeypatch.delenv("OPENHER_API_TOKEN", raising=False)
    import main
    from server.context import AppContext

    return TestClient(main.create_app(AppContext()), raise_server_exceptions=False)


def test_http_responses_include_request_id_and_process_time(monkeypatch):
    client = build_test_client(monkeypatch)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Process-Time-ms"]) >= 0.0


def test_valid_incoming_request_id_is_preserved(monkeypatch):
    client = build_test_client(monkeypatch)

    response = client.get("/api/status", headers={"X-Request-ID": "codex-request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "codex-request-123"


def test_blank_or_unsafe_request_id_is_replaced(monkeypatch):
    client = build_test_client(monkeypatch)

    blank_response = client.get("/api/status", headers={"X-Request-ID": "   "})
    unsafe_response = client.get("/api/status", headers={"X-Request-ID": "bad request id"})

    assert blank_response.status_code == 200
    assert len(blank_response.headers["X-Request-ID"]) == 32
    assert unsafe_response.status_code == 200
    assert unsafe_response.headers["X-Request-ID"] != "bad request id"
    assert len(unsafe_response.headers["X-Request-ID"]) == 32


def test_unauthorized_responses_include_observability_headers(monkeypatch):
    monkeypatch.setenv("OPENHER_API_TOKEN", "secret-token")
    import main
    from server.context import AppContext

    client = TestClient(main.create_app(AppContext()), raise_server_exceptions=False)

    response = client.get("/api/status")

    assert response.status_code == 401
    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Process-Time-ms"]) >= 0.0


def test_main_registers_observability_middleware():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "from server.observability import add_request_observability" in main_source
    assert 'server_app.middleware("http")(add_request_observability)' in main_source
