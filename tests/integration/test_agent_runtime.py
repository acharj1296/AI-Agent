"""Integration tests for the STEP 5 Agent Runtime (requires MongoDB).

Runs against the isolated ``aiagent_test`` database.  The runtime under test is
composed with the same pieces as ``aiagent.services.build_service_layer`` but
receives a *scriptable* deterministic mock provider so retry/failure scenarios
are exercised deterministically.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aiagent.agents.services import AgentRegistryService
from aiagent.core.config import RuntimeSettings, get_settings
from aiagent.core.errors import (
    AgentNotExecutableError,
    InvalidExecutionContextError,
    NotFoundError,
    PayloadTooLargeError,
    PermissionDeniedError,
)
from aiagent.db.constants import AgentRunStatus, AgentStatus
from aiagent.db.models import AgentRun
from aiagent.db.repositories import Repositories
from aiagent.events.audit import AuditLogger
from aiagent.events.publisher import EventPublisher
from aiagent.projects.services import ProjectService
from aiagent.runtime import AgentRuntimeService, ModelGateway, ModelProviderRegistry
from aiagent.runtime.content import FileContentStore
from aiagent.runtime.context import AutonomyDecision, RuntimeRequest
from aiagent.runtime.errors import ModelConfigurationError
from aiagent.runtime.prompts import FileInstructionSource
from aiagent.runtime.providers.mock import DeterministicMockModelProvider, ScriptedBehavior
from aiagent.services import ServiceLayer
from aiagent.tasks.services import TaskService
from aiagent.workflow.services import WorkflowService

pytestmark = pytest.mark.integration

RETRY_MODEL = {
    "provider": "mock",
    "model": "mock-default",
    "retry_policy": {
        "max_attempts": 3,
        "backoff_base_secs": 0,
        "backoff_cap_secs": 0,
        "jitter": False,
    },
}


def _compose_layer(db, *, provider=None, settings=None):
    """Compose a ServiceLayer with a scriptable mock provider for the runtime."""
    repos = Repositories(db)
    publisher = EventPublisher(repos.events)
    audit = AuditLogger(repos.audit_logs)
    cfg = settings or get_settings()
    provider = provider or DeterministicMockModelProvider()
    registry = ModelProviderRegistry()
    registry.register(provider)
    gateway = ModelGateway(registry, settings=cfg.runtime)
    runtime = AgentRuntimeService(
        repos=repos,
        publisher=publisher,
        audit=audit,
        gateway=gateway,
        instructions=FileInstructionSource(Path(cfg.storage.prompts_dir).resolve()),
        content_store=FileContentStore(Path(cfg.storage.artifacts_dir).resolve()),
        settings=cfg.runtime,
    )
    return ServiceLayer(
        projects=ProjectService(repos, publisher, audit),
        agents=AgentRegistryService(repos, publisher, audit),
        tasks=TaskService(repos, publisher, audit),
        workflows=WorkflowService(repos, publisher, audit),
        runtime=runtime,
    )


async def _register_active(
    layer,
    agent_id: str = "rt_agent",
    *,
    slug: str | None = None,
    model=None,
    autonomy=None,
    tools=None,
    capabilities=None,
    status=AgentStatus.REGISTERED,
):
    agent = await layer.agents.register_agent(
        agent_id=agent_id,
        slug=slug or agent_id.replace("_", "-"),
        name=agent_id,
        capabilities=capabilities or ["development.backend"],
        model=model,
        autonomy=autonomy,
        tools=tools,
        status=status,
    )
    if agent.status is AgentStatus.REGISTERED:
        await layer.agents.enable_agent(agent.agent_id)
    return agent


async def _count(db, **query) -> int:
    return await db["agent_runs"].count_documents(query)


# ---------------------------------------------------------------------------
# Happy path / persistence
# ---------------------------------------------------------------------------


async def test_agent_run_success(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_success")
    outcome = await layer.runtime.run(
        RuntimeRequest(
            agent_handle="rt-success", input="write a login flow", correlation_id="corr-abc"
        )
    )
    run: AgentRun = outcome.run
    assert outcome.decision is AutonomyDecision.ALLOWED
    assert run.status is AgentRunStatus.SUCCEEDED
    assert run.agent_id == "rt_success"
    assert run.attempt == 1
    assert run.provider == "mock"
    assert run.model == "mock-default"
    assert run.tokens_in > 0 and run.tokens_out > 0
    assert run.duration_ms is not None
    assert run.correlation_id == "corr-abc"
    assert run.output and run.output.startswith("[mock:")
    assert "login flow" in run.output

    # persisted with previews + lifecycle events
    assert await _count(mongo_db, _id=run.id, status="succeeded") == 1
    assert await mongo_db["events"].find_one({"type": "agent_run.created"})
    assert await mongo_db["events"].find_one({"type": "agent_run.started"})
    assert await mongo_db["events"].find_one({"type": "agent_run.succeeded"})
    assert await mongo_db["audit_logs"].find_one({"action": "agent_run.succeeded"})


async def test_attempts_increment_per_agent(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_attempts")
    for expected in (1, 2, 3):
        outcome = await layer.runtime.run(RuntimeRequest(agent_handle="rt-attempts", input="x"))
        assert outcome.run.attempt == expected


async def test_run_via_agent_id_handle(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_byid")
    outcome = await layer.runtime.run(RuntimeRequest(agent_handle="rt_byid", input="x"))
    assert outcome.run.status is AgentRunStatus.SUCCEEDED


async def test_correlation_and_project_task_metadata_saved(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    from aiagent.db.models import Organization

    org = Organization(name="Runtime Org")
    await layer.runtime._repos.organizations.create(org)
    project = await layer.projects.create_project(org_id=org.id, name="Plat", description=None)
    task = await layer.tasks.create_task(project_id=project.id, task_type="feature", title="Auth")
    await _register_active(layer, "rt_meta")
    outcome = await layer.runtime.run(
        RuntimeRequest(
            agent_handle="rt-meta",
            input="do it",
            project_id=project.id,
            task_id=task.id,
            workflow_run_id="wf-1",
            correlation_id="corr-x",
        )
    )
    assert outcome.run.project_id == project.id
    assert outcome.run.task_id == task.id
    assert outcome.run.workflow_run_id == "wf-1"
    assert outcome.run.correlation_id == "corr-x"
    assert await mongo_db["events"].find_one({"type": "agent_run.succeeded"})


# ---------------------------------------------------------------------------
# Gates + validation failures
# ---------------------------------------------------------------------------


async def test_unknown_agent_raises_not_found(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    with pytest.raises(NotFoundError):
        await layer.runtime.run(RuntimeRequest(agent_handle="nope", input="x"))


async def test_disabled_agent_not_executable(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_disabled")
    await layer.agents.disable_agent("rt_disabled")
    with pytest.raises(AgentNotExecutableError):
        await layer.runtime.run(RuntimeRequest(agent_handle="rt-disabled", input="x"))


async def test_missing_capability_denied(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_cap")
    with pytest.raises(PermissionDeniedError):
        await layer.runtime.run(
            RuntimeRequest(
                agent_handle="rt-cap",
                input="x",
                required_capability="quality.assurance",
            )
        )


async def test_ungranted_tool_denied(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_tool")
    with pytest.raises(PermissionDeniedError):
        await layer.runtime.run(
            RuntimeRequest(agent_handle="rt-tool", input="x", requested_tool_ids=["fs.write"])
        )


async def test_project_not_found_raises_invalid_context(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_ctx")
    with pytest.raises(InvalidExecutionContextError):
        await layer.runtime.run(
            RuntimeRequest(
                agent_handle="rt-ctx",
                input="x",
                project_id="missing-project-000000000000",
            )
        )


async def test_task_not_found_raises_invalid_context(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_ctx2")
    with pytest.raises(InvalidExecutionContextError):
        await layer.runtime.run(
            RuntimeRequest(agent_handle="rt-ctx2", input="x", task_id="missing-task-0000000000000")
        )


async def test_oversized_input_rejected(mongo_db) -> None:
    settings = get_settings()
    settings.runtime = RuntimeSettings(max_input_chars=64, inline_preview_chars=16)
    layer = _compose_layer(mongo_db, settings=settings)
    await _register_active(layer, "rt_big")
    with pytest.raises(PayloadTooLargeError):
        await layer.runtime.run(RuntimeRequest(agent_handle="rt-big", input="B" * 100))
    assert await _count(mongo_db) == 0


async def test_invalid_model_config_aborts_without_run(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(
        layer,
        "rt_badmodel",
        model={"provider": "openai", "model": "gpt-4o"},
    )
    with pytest.raises(ModelConfigurationError):
        await layer.runtime.run(RuntimeRequest(agent_handle="rt-badmodel", input="x"))
    assert await _count(mongo_db) == 0


# ---------------------------------------------------------------------------
# Autonomy / approval-required
# ---------------------------------------------------------------------------


async def test_autonomy_approval_required_pauses_run(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_auto", autonomy={"level": 2})
    outcome = await layer.runtime.run(
        RuntimeRequest(agent_handle="rt-auto", input="x", required_autonomy_level=3)
    )
    assert outcome.decision is AutonomyDecision.APPROVAL_REQUIRED
    assert outcome.run.status is AgentRunStatus.PAUSED
    assert outcome.result is None
    assert await _count(mongo_db, _id=outcome.run.id, status="paused") == 1
    assert await mongo_db["events"].find_one({"type": "agent_run.paused"})


async def test_autonomy_within_level_executes(mongo_db) -> None:
    layer = _compose_layer(mongo_db)
    await _register_active(layer, "rt_auto2", autonomy={"level": 2})
    outcome = await layer.runtime.run(
        RuntimeRequest(agent_handle="rt-auto2", input="x", required_autonomy_level=2)
    )
    assert outcome.decision is AutonomyDecision.ALLOWED
    assert outcome.run.status is AgentRunStatus.SUCCEEDED


# ---------------------------------------------------------------------------
# Provider failure / retry / cancellation
# ---------------------------------------------------------------------------


async def test_retryable_provider_error_succeeds_after_retries(mongo_db) -> None:
    provider = DeterministicMockModelProvider()
    provider.script(
        [ScriptedBehavior.SERVER_ERROR, ScriptedBehavior.SERVER_ERROR, ScriptedBehavior.SUCCESS]
    )
    layer = _compose_layer(mongo_db, provider=provider)
    await _register_active(layer, "rt_retry", model=RETRY_MODEL)
    outcome = await layer.runtime.run(RuntimeRequest(agent_handle="rt-retry", input="x"))
    assert outcome.run.status is AgentRunStatus.SUCCEEDED
    assert outcome.run.retry_count == 2
    assert await mongo_db["events"].find_one({"type": "agent_run.started"})
    assert await mongo_db["events"].find_one({"type": "agent_run.succeeded"})


async def test_retry_exhausted_fails(mongo_db) -> None:
    provider = DeterministicMockModelProvider()
    provider.script([ScriptedBehavior.SERVER_ERROR] * 5)
    layer = _compose_layer(mongo_db, provider=provider)
    await _register_active(layer, "rt_exhaust", model=RETRY_MODEL)
    outcome = await layer.runtime.run(RuntimeRequest(agent_handle="rt-exhaust", input="x"))
    assert outcome.run.status is AgentRunStatus.FAILED
    assert outcome.run.retry_count == 2
    assert outcome.run.error_code == "provider_unavailable"
    assert outcome.run.error_detail
    outcome2 = await layer.runtime.run(RuntimeRequest(agent_handle="rt-exhaust", input="x"))
    assert outcome2.run.attempt == 2


async def test_non_retryable_error_fails_immediately(mongo_db) -> None:
    provider = DeterministicMockModelProvider()
    provider.script([ScriptedBehavior.INVALID] * 5)
    layer = _compose_layer(mongo_db, provider=provider)
    await _register_active(layer, "rt_invalid", model=RETRY_MODEL)
    outcome = await layer.runtime.run(RuntimeRequest(agent_handle="rt-invalid", input="x"))
    assert outcome.run.status is AgentRunStatus.FAILED
    assert outcome.run.retry_count == 0
    assert outcome.run.error_code == "invalid_model_response"


async def test_rate_limit_retries(mongo_db) -> None:
    provider = DeterministicMockModelProvider()
    provider.script([ScriptedBehavior.RATE_LIMIT, ScriptedBehavior.SUCCESS])
    layer = _compose_layer(mongo_db, provider=provider)
    await _register_active(layer, "rt_rl", model=RETRY_MODEL)
    outcome = await layer.runtime.run(RuntimeRequest(agent_handle="rt-rl", input="x"))
    assert outcome.run.status is AgentRunStatus.SUCCEEDED
    assert outcome.run.retry_count == 1


async def test_cancelled_provider_cancels_run(mongo_db) -> None:
    provider = DeterministicMockModelProvider()
    provider.script([ScriptedBehavior.CANCELLED])
    layer = _compose_layer(mongo_db, provider=provider)
    await _register_active(layer, "rt_cancel")
    outcome = await layer.runtime.run(RuntimeRequest(agent_handle="rt-cancel", input="x"))
    assert outcome.run.status is AgentRunStatus.CANCELLED
    assert outcome.run.error_code == "provider_cancelled"
    assert await mongo_db["events"].find_one({"type": "agent_run.cancelled"})


async def test_timeout_retries_then_succeeds(mongo_db) -> None:
    provider = DeterministicMockModelProvider()
    provider.script([ScriptedBehavior.TIMEOUT, ScriptedBehavior.SUCCESS])
    layer = _compose_layer(mongo_db, provider=provider)
    await _register_active(layer, "rt_timeout", model=RETRY_MODEL)
    outcome = await layer.runtime.run(RuntimeRequest(agent_handle="rt-timeout", input="x"))
    assert outcome.run.status is AgentRunStatus.SUCCEEDED
    assert outcome.run.retry_count == 1
