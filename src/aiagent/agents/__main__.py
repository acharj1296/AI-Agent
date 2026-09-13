"""Standalone system-agent seeding.

Used by ``python -m aiagent.agents`` (see the Makefile ``seed`` target).

Idempotent on purpose: existing agents (by slug or agent_id) are skipped and
manual configuration is never overwritten, so this can be re-run safely.
"""

from __future__ import annotations

import asyncio

from aiagent.core.config import load_settings
from aiagent.db.session import close_db, init_db
from aiagent.services import build_service_layer


async def _run() -> None:
    settings = load_settings()
    db = await init_db(settings)
    layer = build_service_layer(db)
    agents = await layer.agents.run_seed()
    print(f"seeded {len(agents)} system agents in '{settings.db.name}':")
    for agent in agents:
        print(f"  - {agent.slug} ({agent.agent_id}) [{agent.status.value}] v{agent.version}")
    await close_db()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
