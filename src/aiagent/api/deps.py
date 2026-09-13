"""Re-usable FastAPI dependencies.

Router files use ``from aiagent.api.deps import DbDep, SettingsDep`` to retrieve
the validated config and the configured MongoDB database handle, and
``ServicesDep`` for the assembled service layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from aiagent.core.config import Settings, get_settings
from aiagent.db.session import get_db
from aiagent.services import ServiceLayer, build_service_layer


async def _get_settings() -> Settings:
    return get_settings()


async def _get_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    async for database in get_db():
        yield database


def _get_services(database: DbDep) -> ServiceLayer:
    return build_service_layer(database)


SettingsDep = Annotated[Settings, Depends(_get_settings)]
DbDep = Annotated[AsyncIOMotorDatabase, Depends(_get_db)]
ServicesDep = Annotated[ServiceLayer, Depends(_get_services)]
