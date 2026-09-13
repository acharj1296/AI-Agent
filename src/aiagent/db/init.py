"""Standalone MongoDB initialization (collections + indexes).

Used by the ``python -m aiagent.db`` command (see ``scripts/migrate.ps1`` and
the ``Makefile`` migrate target) and by the application startup path via
:func:`aiagent.db.session.init_db`.
"""

from __future__ import annotations

import asyncio

from aiagent.core.config import load_settings
from aiagent.db.session import close_db, init_db


async def _run() -> None:
    settings = load_settings()
    db = await init_db(settings)
    names = sorted(await db.list_collection_names())
    print(f"database '{settings.db.name}' initialized; collections: {', '.join(names)}")
    await close_db()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
