"""Integration tests for the STEP 3 service layer, events and audit trails.

Requires a reachable MongoDB (skipped otherwise); runs against the isolated
``aiagent_test`` database provided by the shared ``mongo_db`` fixture.
"""

from __future__ import annotations

import pytest

from aiagent.core.errors import ConflictError, NotFoundError
from aiagent.db.constants import (
    ProjectStage,
    ProjectStatus,
    TaskRunStatus,
    WorkflowRunStatus,
    WorkflowStatus,
)
from aiagent.db.models import Organization, Project
from aiagent.db.repositories import Repositories
from aiagent.events import AuditLogger, DomainEvent, EventPublisher, EventType
from aiagent.services import ServiceLayer, build_service_layer

pytestmark = pytest.mark.integration


async def _seed_org(db) -> Organization:
    repos = Repositories(db)
    org = Organization(name="Acme Services")
    await repos.organizations.create(org)
    return org


async def _seeded_layer(db) -> tuple[ServiceLayer, Organization]:
    org = await _seed_org(db)
    return build_service_layer(db), org


async def test_project_onboarding_emits_event_and_audit(mongo_db) -> None:
    layer, org = await _seeded_layer(mongo_db)

    project = await layer.projects.create_project(
        org_id=org.id,
        name="Weather API",
        description="demo onboarding",
        autonomy_level=2,
        decisions=[{"title": "use mongo"}],
        facts=[{"key": "db", "value": "mongo"}],
    )

    assert project.org_id == org.id
    assert project.stage == ProjectStage.IDEA
    assert project.status == ProjectStatus.ACTIVE
    assert project.decisions[0]["title"] == "use mongo"

    event = await mongo_db["events"].find_one({"type": "project.created", "project_id": project.id})
    assert event is not None
    assert event["status"] == "pending"
    assert event["emitted_by"]["service"] == "service:project"

    audit = await mongo_db["audit_logs"].find_one(
        {"action": "project.create", "resource_id": project.id}
    )
    assert audit is not None
    assert audit.get("before") is None
    assert audit["after"]["name"] == "Weather API"


async def test_project_service_rejects_missing_org(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    with pytest.raises(NotFoundError):
        await layer.projects.create_project(org_id="0" * 32, name="Orphan")


async def test_project_status_change_audits_before_after(mongo_db) -> None:
    layer, org = await _seeded_layer(mongo_db)
    project = await layer.projects.create_project(org_id=org.id, name="P")

    updated = await layer.projects.change_status(project.id, status=str(ProjectStatus.PAUSED))
    assert updated.status == ProjectStatus.PAUSED

    audit = await mongo_db["audit_logs"].find_one(
        {"action": "project.status_change", "resource_id": project.id}
    )
    assert audit["before"]["status"] == "active"
    assert audit["after"]["status"] == "paused"

    event = await mongo_db["events"].find_one({"type": "project.updated", "project_id": project.id})
    assert event["payload"]["before"] == "active"
    assert event["payload"]["after"] == "paused"


async def test_task_service_full_run_lifecycle(mongo_db) -> None:
    layer, org = await _seeded_layer(mongo_db)
    project = await layer.projects.create_project(org_id=org.id, name="P")
    task = await layer.tasks.create_task(
        project_id=project.id,
        task_type="dev",
        title="implement feature",
        priority="high",
    )
    assert task.type == "dev"
    assert (await mongo_db["events"].find_one({"type": "task.created"})) is not None

    run = await layer.tasks.start_task_run(task_id=task.id)
    assert run.attempt == 1
    assert run.status == TaskRunStatus.RUNNING
    assert run.started_at is not None
    assert (await mongo_db["events"].find_one({"type": "task_run.started"})) is not None

    # attempt numbering is unique per task
    with pytest.raises(ConflictError):
        await layer.tasks.start_task_run(task_id=task.id, attempt=1)

    done = await layer.tasks.finish_task_run(run.id, status=TaskRunStatus.SUCCEEDED)
    assert done.status == TaskRunStatus.SUCCEEDED
    assert done.completed_at is not None
    assert (await mongo_db["events"].find_one({"type": "task_run.completed"})) is not None

    second = await layer.tasks.start_task_run(task_id=task.id)
    assert second.attempt == 2

    failed = await layer.tasks.finish_task_run(
        second.id, status=TaskRunStatus.FAILED, error_detail={"reason": "lint failed"}
    )
    assert failed.error_detail == {"reason": "lint failed"}
    assert (await mongo_db["events"].find_one({"type": "task_run.failed"})) is not None


async def test_task_service_rejects_missing_project(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    with pytest.raises(NotFoundError):
        await layer.tasks.create_task(project_id="0" * 32, task_type="dev", title="T")
    with pytest.raises(NotFoundError):
        await layer.tasks.start_task_run(task_id="0" * 32)


async def test_workflow_service_register_versions_and_run(mongo_db) -> None:
    layer, org = await _seeded_layer(mongo_db)
    project = await layer.projects.create_project(org_id=org.id, name="P")

    wf = await layer.workflows.register_workflow(
        workflow_id="project_build",
        name="Project build",
        version=1,
        entry="validate_idea",
        steps=[{"id": "validate_idea", "type": "stage_gate"}],
    )
    assert wf.status == WorkflowStatus.DRAFT
    assert (await mongo_db["events"].find_one({"type": "workflow.registered"})) is not None

    with pytest.raises(ConflictError):
        await layer.workflows.register_workflow(workflow_id="project_build", name="X", version=1)

    await layer.workflows.register_workflow(
        workflow_id="project_build", name="Project build v2", version=2
    )
    run = await layer.workflows.create_workflow_run(
        project_id=project.id, workflow_id="project_build"
    )
    assert run.status == WorkflowRunStatus.CREATED
    assert (await mongo_db["events"].find_one({"type": "workflow_run.created"})) is not None

    with pytest.raises(NotFoundError):
        await layer.workflows.create_workflow_run(project_id=project.id, workflow_id="unknown")
    with pytest.raises(NotFoundError):
        await layer.workflows.create_workflow_run(project_id="0" * 32, workflow_id="project_build")


async def test_agent_service_register_update_and_audit_diff(mongo_db) -> None:
    layer = build_service_layer(mongo_db)

    agent = await layer.agents.register_agent(
        agent_id="dev_backend",
        department="development",
        name="Backend Developer",
        config={"model_profile": "default_coding"},
    )
    assert (await mongo_db["events"].find_one({"type": "agent.created"})) is not None

    with pytest.raises(ConflictError):
        await layer.agents.register_agent(agent_id="dev_backend")

    updated = await layer.agents.update_agent(
        agent.id, name="Backend Dev v2", config={"model_profile": "fast_coding"}
    )
    assert updated.name == "Backend Dev v2"

    audit = await mongo_db["audit_logs"].find_one(
        {"action": "agent.update", "resource_id": agent.id}
    )
    assert audit["before"]["name"] == "Backend Developer"
    assert audit["after"]["name"] == "Backend Dev v2"
    assert (await mongo_db["events"].find_one({"type": "agent.updated"})) is not None


async def test_repository_pagination_against_real_mongo(mongo_db) -> None:
    repos = Repositories(mongo_db)
    org = await _seed_org(mongo_db)
    for index in range(25):
        await repos.projects.create(Project(org_id=org.id, name=f"P{index:02d}"))

    first = await repos.projects.paginate(
        {"org_id": org.id}, sort=[("created_at", -1)], page=1, page_size=10
    )
    assert len(first.items) == 10
    assert first.total == 25
    assert first.has_next is True

    last = await repos.projects.paginate(
        {"org_id": org.id}, sort=[("created_at", -1)], page=3, page_size=10
    )
    assert len(last.items) == 5
    assert last.has_next is False

    clamped = await repos.projects.paginate({"org_id": org.id}, page=0, page_size=0)
    assert clamped.page == 1
    assert clamped.page_size == 1
    assert len(clamped.items) == 1


async def test_event_publisher_writes_pending_outbox(mongo_db) -> None:
    from aiagent.core.context import clear_request_context, set_request_context

    repos = Repositories(mongo_db)
    publisher = EventPublisher(repos.events)

    set_request_context(request_id="rid-x", trace_id="trace-x")
    event = DomainEvent.build(
        EventType.PROJECT_UPDATED,
        payload={"project_id": "p" * 32},
        project_id="p" * 32,
        emitted_by="service:test",
    )
    await publisher.publish(event)
    clear_request_context()

    doc = await mongo_db["events"].find_one({"type": "project.updated"})
    assert doc is not None
    assert doc["status"] == "pending"
    assert doc["trace_id"] == "trace-x"
    assert doc["emitted_by"]["service"] == "service:test"


async def test_audit_logger_writes_before_after(mongo_db) -> None:
    audit = AuditLogger(Repositories(mongo_db).audit_logs)
    entry = await audit.record(
        action="test.audit",
        resource_type="project",
        resource_id="p" * 32,
        before={"a": 1},
        after={"a": 2},
    )
    doc = await mongo_db["audit_logs"].find_one({"_id": entry.id})
    assert doc is not None
    assert doc["before"] == {"a": 1}
    assert doc["after"] == {"a": 2}
