"""Shared pytest fixtures.

An autouse fixture resets the process-wide settings cache and the global
MongoDB client so every test starts from a clean, lazy state.  Unit tests (any
test *not* marked ``integration``) additionally stub out the network-touching
``aiagent.api.app.init_db`` so they never require a running MongoDB.

``mongo_db`` provides an isolated ``aiagent_test`` database for integration
tests (dropped after every test) and skips when MongoDB is unreachable.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from aiagent.core.config import SETTINGS_CACHE_CLEAR, Settings
from aiagent.db.client import create_client, ping_client
from aiagent.db.session import close_db, init_db

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"

TEST_DB = "aiagent_test"


async def _mongo_reachable(max_seconds: int = 3) -> bool:
    settings = Settings.load(env_override="dev")
    settings.db.name = "admin"
    settings.db.server_selection_timeout_ms = max_seconds * 1000
    client = create_client(settings.db)
    try:
        return await ping_client(client)
    finally:
        client.close()


@pytest.fixture(autouse=True)
def _reset_process_state():
    SETTINGS_CACHE_CLEAR()
    asyncio.run(close_db())
    yield
    asyncio.run(close_db())
    SETTINGS_CACHE_CLEAR()


@pytest.fixture(autouse=True)
def _offline_database(monkeypatch, request):
    """Keep FastAPI liveness spans offline for unit tests.

    Integration tests exercise the real ``init_db`` startup path.
    """
    if "integration" in request.keywords:
        yield
        return

    async def _noop_init(settings) -> None:
        return None

    monkeypatch.setattr("aiagent.api.app.init_db", _noop_init)
    yield


@pytest.fixture
async def mongo_db():
    """Isolated integration-test database, dropped after every test."""
    if not await _mongo_reachable():
        pytest.skip("MongoDB is not reachable (is the local stack running?)")

    settings = Settings.load(env_override="dev")
    settings.db.name = TEST_DB
    db = await init_db(settings)
    yield db

    # Isolated test database: drop it entirely after the test using a fresh
    # client (the shared one may have been closed by an app lifespan).
    client = create_client(settings.db)
    try:
        await client.drop_database(TEST_DB)
    finally:
        client.close()
    await close_db()
