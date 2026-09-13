"""HTTP-level integration tests for the STEP 4 Agent Registry API.

Requires a reachable MongoDB (skipped otherwise).  The app runs against the
isolated ``aiagent_test`` database via its own event loop (the collections are
recreated per run inside the TestClient lifespan).
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
    """Drop the isolated test database using a throwaway client.

    Runs before every test so leftovers from earlier tests cannot leak into
    assertions (the app uses the shared process client from its own loop, so
    cleanup must use a fresh client that is opened and closed here).
    """
    settings = Settings.load(env_override="dev")
    settings.db.name = "aiagent_test"
    client = create_client(settings.db)

    async def _drop() -> None:
        await client.drop_database("aiagent_test")

    try:
        asyncio.run(_drop())
    finally:
        client.close()


def _create(client: TestClient, **overrides) -> dict:
    payload = {
        "agent_id": "api_dev",
        "name": "API Developer",
        "slug": "api-developer",
        "role": "developer",
        "department": "development",
        "status": "registered",
        "capabilities": ["development.backend"],
    }
    payload.update(overrides)
    return client.post("/agents", json=payload)


def test_list_and_create_roundtrip() -> None:
    _reset_db()
    with _client() as client:
        empty = client.get("/agents")
        assert empty.status_code == 200
        assert empty.json()["ok"] is True
        assert empty.json()["data"]["items"] == []

        created = _create(client)
        assert created.status_code == 201
        assert created.json()["data"]["slug"] == "api-developer"
        assert created.json()["data"]["status"] == "registered"

        fetched = client.get("/agents/api-developer")
        assert fetched.status_code == 200
        assert fetched.json()["data"]["agent_id"] == "api_dev"
        assert fetched.json()["data"]["capabilities"] == ["development.backend"]

        listing = client.get("/agents", params={"status": "registered"})
        assert len(listing.json()["data"]["items"]) == 1


def test_duplicate_agent_id_conflicts_with_envelope() -> None:
    _reset_db()
    with _client() as client:
        _create(client, agent_id="dup_agent", slug="dup-agent")
        resp = _create(client, agent_id="dup_agent", slug="other-slug")
        assert resp.status_code == 409
        assert resp.json()["ok"] is False
        assert resp.json()["error"]["code"] == "conflict"


def test_invalid_slug_rejected_422() -> None:
    _reset_db()
    with _client() as client:
        resp = _create(client, agent_id="bad_slug_agent", slug="Not A Slug")
        assert resp.status_code == 422
        assert resp.json()["ok"] is False


def test_unknown_agent_404_envelope() -> None:
    _reset_db()
    with _client() as client:
        resp = client.get("/agents/nope-not-here")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"


def test_update_and_lifecycle_via_api() -> None:
    _reset_db()
    with _client() as client:
        _create(client, agent_id="life_api", slug="life-api", status="active")

        patched = client.patch(
            "/agents/life-api",
            json={"name": "Life API v2", "permissions": {"filesystem": {"read_root": "docs/"}}},
        )
        assert patched.status_code == 200
        assert patched.json()["data"]["name"] == "Life API v2"
        assert patched.json()["data"]["version"] == "1.0.1"

        # active -> enable is not a valid transition -> 409
        again = client.post("/agents/life-api/enable")
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "invalid_state"

        disabled = client.post("/agents/life-api/disable")
        assert disabled.status_code == 200
        assert disabled.json()["data"]["status"] == "disabled"

        # disabling twice is invalid -> 409
        again = client.post("/agents/life-api/disable")
        assert again.status_code == 409

        reenabled = client.post("/agents/life-api/enable")
        assert reenabled.json()["data"]["status"] == "active"

        deprecated = client.post("/agents/life-api/deprecate")
        assert deprecated.json()["data"]["status"] == "deprecated"

        # deprecated is terminal
        doomed = client.post("/agents/life-api/enable")
        assert doomed.status_code == 409


def test_update_rejects_status_field() -> None:
    _reset_db()
    with _client() as client:
        _create(client, agent_id="no_status", slug="no-status")
        resp = client.patch("/agents/no-status", json={"status": "active"})
        assert resp.status_code == 422  # extra="forbid" on the request model


def test_eligible_and_capability_endpoints() -> None:
    _reset_db()
    with _client() as client:
        _create(client, agent_id="corp", slug="corp", status="active")
        resp = client.get(
            "/agents/eligible", params={"required_capabilities": ["development.backend"]}
        )
        assert resp.status_code == 200
        assert [a["agent_id"] for a in resp.json()["data"]] == ["corp"]

        by_capability = client.get("/agents/capability/development.backend")
        assert by_capability.status_code == 200
        assert by_capability.json()["data"][0]["slug"] == "corp"


def test_public_payload_never_exposes_material() -> None:
    """The public definition shape must not leak secret values."""
    _reset_db()
    with _client() as client:
        created = _create(client)
        slug = created.json()["data"]["slug"]
        body = client.get(f"/agents/{slug}").json()["data"]

        # If a secrets block is declared, it may only hold NAMES, never values.
        secrets = (body.get("permissions") or {}).get("secrets") or {}
        assert not any(
            key.lower() in {"value", "secret", "token", "api_key_value"} for key in secrets
        )
        assert "system_prompt_ref" not in body or (
            body["system_prompt_ref"] is None or body["system_prompt_ref"].startswith("system/")
        )
