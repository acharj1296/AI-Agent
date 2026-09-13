"""Shared pytest fixtures.

An autouse fixture resets the process-wide settings cache and the global
MongoDB client so every test starts from a clean, lazy state.  Unit tests (any
test *not* marked ``integration``) additionally stub out the network-touching
``aiagent.api.app.init_db`` so they never require a running MongoDB.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from aiagent.core.config import SETTINGS_CACHE_CLEAR
from aiagent.db.session import close_db

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


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
