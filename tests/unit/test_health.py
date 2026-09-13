"""Unit tests for the health endpoints and error envelope."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aiagent.api.app import create_app
from aiagent.api.envelope import error, ok
from aiagent.core import context
from aiagent.core.config import Settings
from aiagent.core.errors import NotFoundError


def _client() -> TestClient:
    app = create_app(Settings.load(env_override="dev"))
    return TestClient(app)


def test_healthz_liveness() -> None:
    with _client() as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["status"] == "ok"
        assert body["data"]["service"] == "aiagent"
        assert body["data"]["timestamp"]
        assert body["trace_id"]


def test_root_says_service() -> None:
    with _client() as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["data"]["service"] == "aiagent"
        assert resp.headers["X-Trace-ID"]


def test_readyz_reports_not_ready_when_db_down(monkeypatch) -> None:
    async def ping_down() -> bool:
        return False

    monkeypatch.setattr("aiagent.api.routers.health.ping", ping_down)
    with _client() as client:
        resp = client.get("/readyz")
        assert resp.status_code == 503
        body = resp.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "not_ready"


def test_readyz_reports_ready_when_db_up(monkeypatch) -> None:
    async def ping_up() -> bool:
        return True

    monkeypatch.setattr("aiagent.api.routers.health.ping", ping_up)
    with _client() as client:
        resp = client.get("/readyz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["checks"]["database"] == "ok"
        assert body["data"]["timestamp"]


def test_unknown_route_returns_error_envelope() -> None:
    with _client() as client:
        resp = client.get("/v1/does-not-exist")
        assert resp.status_code == 404
        body = resp.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "http_error"


def test_domain_error_maps_to_envelope() -> None:
    app = create_app(Settings.load(env_override="dev"))

    @app.get("/boom")
    async def boom() -> None:
        raise NotFoundError("project 123 not found", details={"id": "123"})

    with TestClient(app) as client:
        resp = client.get("/boom")
        assert resp.status_code == 404
        body = resp.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "not_found"
        assert body["error"]["message"] == "project 123 not found"
        assert body["error"]["details"] == {"id": "123"}


def test_envelope_builders() -> None:
    context.set_request_context(trace_id="trace-abc")
    try:
        success = ok({"a": 1}, meta={"page": 1})
        assert success["ok"] is True
        assert success["data"] == {"a": 1}
        assert success["meta"] == {"page": 1}
        assert success["trace_id"] == "trace-abc"

        failure = error(code="validation_error", message="bad input", details=[1, 2])
        assert failure["ok"] is False
        assert failure["error"]["code"] == "validation_error"
        assert failure["error"]["details"] == [1, 2]
        assert failure["trace_id"] == "trace-abc"
    finally:
        context.clear_request_context()
