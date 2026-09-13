"""Application-level MongoDB lifecycle: connect, verify, initialize, ping.

Keeps the same public names as the STEP-1 module (``init_db`` / ``close_db`` /
``ping`` / ``get_db``) so the FastAPI app wiring changes minimally while the
backend switches from SQLAlchemy/PostgreSQL to Motor/MongoDB.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from aiagent.core.config import Settings
from aiagent.core.errors import DatabaseConnectionError, DatabaseError
from aiagent.core.logging import get_logger
from aiagent.db.client import close_client, create_client, ping_client, redact_uri
from aiagent.db.indexes import ensure_collections_and_indexes

logger = get_logger("db")

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def init_db(settings: Settings) -> AsyncIOMotorDatabase:
    """Connect to MongoDB, verify availability, and initialize collections+indexes.

    Fail-fast: raises :class:`DatabaseConnectionError` when the server cannot be
    reached instead of pretending the database is available.
    """
    global _client, _database
    if _client is None:
        _client = create_client(settings.db)
    _database = _client[settings.db.name]

    if not await ping_client(_client):
        await close_db()
        raise DatabaseConnectionError(f"database '{settings.db.name}' unavailable at startup")

    await ensure_collections_and_indexes(_database)
    logger.info(
        "database initialized",
        extra={"database": settings.db.name, "uri": redact_uri(settings.db.uri)},
    )
    return _database


async def close_db() -> None:
    """Release the client and drop global references (graceful shutdown)."""
    global _client, _database
    if _client is not None:
        close_client(_client)
    _client = None
    _database = None


async def ping() -> bool:
    """Return ``True`` when MongoDB answers ``ping``, ``False`` otherwise."""
    if _client is None:
        return False
    try:
        return await ping_client(_client)
    except Exception:  # noqa: BLE001 - any failure means "not ready"
        logger.warning("database ping failed")
        return False


def get_database() -> AsyncIOMotorDatabase:
    """Return the configured database (call after :func:`init_db`)."""
    if _client is None or _database is None:
        raise DatabaseError("database not initialized; call init_db(settings) during app startup")
    return _database


async def get_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    """FastAPI dependency yielding the configured MongoDB database."""
    yield get_database()
