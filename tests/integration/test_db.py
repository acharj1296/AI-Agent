"""Integration tests requiring a reachable MongoDB instance.

These are skipped automatically when MongoDB is not reachable (e.g. Docker
daemon not running). Run the local stack first:

    docker compose -f deploy/environments/local/docker-compose.yaml up -d mongodb

All tests run against an isolated ``aiagent_test`` database which is dropped
after every test - nothing is ever written to a production database.  Async
fixtures/tests share the pytest-asyncio event loop, which is exactly the loop
the Motor client binds to, so cross-loop usage cannot occur.

The shared ``mongo_db`` fixture lives in ``tests/conftest.py`` so both
``test_db.py`` and ``test_services.py`` share one definition.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from aiagent.api.app import create_app
from aiagent.core.config import Settings
from aiagent.core.errors import ConflictError, DatabaseConnectionError
from aiagent.db.constants import ModelProvider, TaskStatus, UserRole
from aiagent.db.indexes import MVP_COLLECTIONS, ensure_collections_and_indexes
from aiagent.db.models import AgentRun, Model, Organization, Project, Task, User
from aiagent.db.repositories import Repositories
from aiagent.db.session import close_db, init_db, ping

TEST_DB = "aiagent_test"

pytestmark = pytest.mark.integration


async def test_ping_true_when_mongo_up(mongo_db) -> None:
    assert await ping() is True


async def test_init_created_mvp_collections(mongo_db) -> None:
    existing = set(await mongo_db.list_collection_names())
    assert set(MVP_COLLECTIONS) <= existing
    # deferred collections must NOT exist yet
    for deferred in (
        "providers",
        "knowledge",
        "deployments",
        "environments",
        "incidents",
        "test_runs",
    ):
        assert deferred not in existing


async def test_indexes_created_with_unique_flags(mongo_db) -> None:
    await ensure_collections_and_indexes(mongo_db)

    users = {idx["name"]: idx for idx in await mongo_db["users"].list_indexes().to_list(None)}
    assert users["uq_users_email"]["unique"] is True
    assert "ix_users_org_id" in users

    models = {idx["name"]: idx for idx in await mongo_db["models"].list_indexes().to_list(None)}
    assert models["uq_models_model_id"]["unique"] is True

    artifacts = {
        idx["name"]: idx for idx in await mongo_db["artifacts"].list_indexes().to_list(None)
    }
    assert artifacts["uq_artifacts_project_name_version"]["unique"] is True

    events = {idx["name"]: idx for idx in await mongo_db["events"].list_indexes().to_list(None)}
    assert "ix_events_status_created" in events


async def test_repository_roundtrip_and_unique_constraint(mongo_db) -> None:
    repos = Repositories(mongo_db)

    org = Organization(name="Acme", autonomy_default=2)
    created = await repos.organizations.create(org)
    assert created.id == org.id
    assert await repos.organizations.exists({"name": "Acme"}) is True
    assert await repos.organizations.count() == 1

    fetched = await repos.organizations.find_by_id(org.id)
    assert fetched is not None
    assert fetched.name == "Acme"
    assert fetched.autonomy_default == 2

    updated = await repos.organizations.update(org.id, {"name": "Acme Labs"})
    assert updated is not None
    assert updated.name == "Acme Labs"
    assert updated.updated_at >= created.updated_at

    user = User(org_id=org.id, name="Ada", email="ada@acme.example", role=UserRole.ADMIN)
    await repos.users.create(user)
    at = await repos.users.find_by_email("ada@acme.example")
    assert at is not None and at.org_id == org.id
    assert [u.email for u in await repos.users.find_by_org(org.id)] == ["ada@acme.example"]

    with pytest.raises(ConflictError):
        await repos.users.create(
            User(org_id=org.id, name="Ada-2", email="ada@acme.example", role=UserRole.REVIEWER)
        )

    project = Project(
        org_id=org.id,
        name="P1",
        description="hello",
        autonomy_level=2,
        decisions=[{"title": "use mongo"}],
        facts=[{"key": "db", "value": "mongo"}],
    )
    await repos.projects.create(project)
    listed = await repos.projects.find_by_org(org.id)
    assert [p.name for p in listed] == ["P1"]
    active = await repos.projects.find_by_org(org.id, status="active")
    assert len(active) == 1

    task = Task(project_id=project.id, type="dev", title="implement", priority="high")
    await repos.tasks.create(task)
    tasks = await repos.tasks.find_by_project(project.id, status=str(TaskStatus.CREATED))
    assert [t.title for t in tasks] == ["implement"]

    model = Model(model_id="gpt-4o-mini", provider=ModelProvider.OPENAI, enabled=True)
    await repos.models.create(model)
    assert (await repos.models.find_one({"model_id": "gpt-4o-mini"})) is not None

    # clean up test data inside the test database
    await repos.tasks.delete(task.id)
    await repos.projects.delete(project.id)
    await repos.users.delete(user.id)
    await repos.models.delete(model.id)
    assert await repos.organizations.delete(org.id) is True


async def test_validation_rejects_invalid_document_via_repository(mongo_db) -> None:
    repos = Repositories(mongo_db)
    with pytest.raises(ValidationError):
        await repos.agent_runs.create(AgentRun(agent_id="a1", status="not-a-status"))


async def test_repository_lookup_missing_returns_none(mongo_db) -> None:
    repos = Repositories(mongo_db)
    assert await repos.projects.find_by_id("does-not-exist") is None
    assert await repos.projects.update("does-not-exist", {"name": "x"}) is None
    assert await repos.projects.delete("does-not-exist") is False
    assert await repos.projects.count() == 0


async def test_init_db_fails_fast_when_unreachable() -> None:
    await close_db()  # avoid reusing a live global client from earlier tests
    settings = Settings.load(env_override="dev")
    settings.db.uri = "mongodb://127.0.0.1:27099/nope"
    settings.db.name = TEST_DB
    settings.db.server_selection_timeout_ms = 1000
    with pytest.raises(DatabaseConnectionError):
        await init_db(settings)


async def test_readyz_against_real_mongo(mongo_db) -> None:
    """The readiness check reflects a real MongoDB connection.

    Uses httpx ASGITransport so requests run on the pytest-asyncio loop (the
    loop the Motor client is bound to) and no lifespan is triggered - the
    fixture has already initialized the database.
    """
    from aiagent.api.routers.health import ping as health_ping

    assert await health_ping() is True  # the data the endpoint relays

    settings = Settings.load(env_override="dev")
    settings.db.name = TEST_DB
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/readyz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["checks"]["database"] == "ok"
        assert body["data"]["timestamp"]
        assert "uri" not in str(resp.json()).lower()
        health = await client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["data"]["timestamp"]
