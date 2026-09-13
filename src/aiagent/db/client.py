"""Low-level async MongoDB client lifecycle (Motor).

Kept free of business logic: constructing a client, probing it with
``ping``, and closing it.  Composition/initialization lives in
:mod:`aiagent.db.session` / :mod:`aiagent.db.init`.
"""

from __future__ import annotations

import re
from datetime import UTC
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from aiagent.core.config import DBSettings

_CREDENTIALS_RE = re.compile(r"(?<=://)[^/@\s]+@", flags=re.IGNORECASE)
# For SRV URIs the credentials sit after mongodb+srv:// ; the same regex handles it.


def create_client(settings: DBSettings) -> AsyncIOMotorClient[Any]:
    """Create (but do not connect) an async client from validated settings."""
    return AsyncIOMotorClient(
        settings.uri,
        serverSelectionTimeoutMS=settings.server_selection_timeout_ms,
        connectTimeoutMS=settings.connect_timeout_ms,
        maxPoolSize=settings.max_pool_size,
        minPoolSize=settings.min_pool_size,
        tz_aware=True,
        tzinfo=UTC,
    )


async def ping_client(client: AsyncIOMotorClient) -> bool:
    """Return ``True`` if the server replies to ``ping``.  Never raises."""
    try:
        await client.admin.command("ping")
    except PyMongoError:
        return False
    return True


def close_client(client: AsyncIOMotorClient) -> None:
    """Synchronously release the client's sockets and worker tasks."""
    client.close()


def redact_uri(uri: str) -> str:
    """Strip credentials from a URI for logging (never log connection strings)."""
    return _CREDENTIALS_RE.sub("***@", uri)
