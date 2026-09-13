"""HTTP-level integration tests for the STEP 5 internal runtime API.

Requires a reachable MongoDB (skipped otherwise).  Tests execute real agent runs
using the deterministic mock provider wired through ``aiagent.services.
build_service_layer``.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from aiagent.api.app import create_app
from aiagent.core.config import Settings
from aiagent.db.client import create_client, ping_client

logging.getLogger("pymongo").setLevel(logging.CRITICAL)

pytestmark = pytest.mark.integration


def _mongo_available() -> bool:
    settings = Settings.load(env_override="dev")
    settings.db.name = "admin"
    settings.db.server_selection_timeout_ms = 3000
    client = create_client(settings.db)

    async def _ping() -> bool:
        return await ping_client(client)

    try:
        return asyncio.run(_ping())
    finally:
        client.close()


if not _mongo_available():
    pytest.skip("MongoDB is not reachable (is the local stack running?)", allow_module_level=True)


def _client() -> TestClient:
    settings = Settings.load(env_override="dev")
    settings.db.name = "aiagent_test"
    return TestClient(create_app(settings))


def _reset_db() -> None:
    settings = Settings.load(env_override="dev")
    settings.db.name = "aiagent_test"
    client = create_client(settings.db)

    async def _drop() -> None:
        await client.drop_database("aiagent_test")

    try:
        asyncio.run(_drop())
    finally:
        client.close()


def _register_agent(client: TestClient, *, agent_id="api_rt_dev", slug=None):
    resp = client.post(
        "/agents",
        json={
            "agent_id": agent_id,
            "slug": slug or agent_id.replace("_", "-"),
            "name": agent_id,
            "status": "registered",
            "capabilities": ["development.backend"],
            "autonomy": {"level": 2},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _enable(client: TestClient, slug: str) -> dict:
    resp = client.post(f"/agents/{slug}/enable")
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_success_api_flow() -> None:
    _reset_db()
    with _client() as c:
        agent = _register_agent(c)
        _enable(c, agent["slug"])

        run_resp = c.post(f"/internal/agents/{agent['slug']}/run", json={"input": "deploy service"})
        assert run_resp.status_code == 200, run_resp.text
        run_data = run_resp.json()["data"]
        assert run_data["decision"] == "allowed"
        assert run_data["status"] == "succeeded"
        assert run_data["provider"] == "mock"
        assert run_data["tokens_in"] > 0 and run_data["tokens_out"] > 0
        assert "deploy service" in run_data["output"]
        run_id = run_data["run_id"]

        get_resp = c.get(f"/internal/agent-runs/{run_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["run_id"] == run_id


def test_approval_required_returns_paused() -> None:
    _reset_db()
    with _client() as c:
        agent = _register_agent(c, agent_id="api_rt_pa", slug="api-rt-pa")
        _enable(c, agent["slug"])
        run_resp = c.post(
            f"/internal/agents/{agent['slug']}/run",
            json={"input": "x", "required_autonomy_level": 3},
        )
        assert run_resp.status_code == 200, run_resp.text
        assert run_resp.json()["data"]["decision"] == "approval_required"
        assert run_resp.json()["data"]["status"] == "paused"


def test_disabled_agent_not_executable_api() -> None:
    _reset_db()
    with _client() as c:
        agent = _register_agent(c, agent_id="api_rt_dis", slug="api-rt-dis")
        _enable(c, agent["slug"])
        c.post(f"/agents/{agent['slug']}/disable")
        resp = c.post(f"/internal/agents/{agent['slug']}/run", json={"input": "x"})
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "agent_not_executable"


def test_missing_agent_not_found() -> None:
    _reset_db()
    with _client() as c:
        resp = c.post("/internal/agents/nope/run", json={"input": "x"})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"


def test_unknown_run_not_found() -> None:
    _reset_db()
    with _client() as c:
        resp = c.get("/internal/agent-runs/nonexistent")
        assert resp.status_code == 404
