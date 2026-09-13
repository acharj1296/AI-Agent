"""Execution gates + context building for the runtime (docs/plan/36, 45)."""

from __future__ import annotations

import pytest

from aiagent.core.errors import (
    AgentNotExecutableError,
    PayloadTooLargeError,
    PermissionDeniedError,
)
from aiagent.db.constants import AgentStatus
from aiagent.db.models import Agent, AutonomyConfig, ToolSet
from aiagent.runtime.context import (
    AutonomyDecision,
    ExecutionLimits,
    RuntimeRequest,
    build_context,
    check_autonomy,
    check_capability,
    check_permissions,
    check_status,
    validate_input_size,
)


def _agent(**overrides) -> Agent:
    kwargs = {
        "agent_id": "test_agent",
        "name": "Test Agent",
        "slug": "test-agent",
        "status": AgentStatus.ACTIVE,
        "capabilities": ["development.backend"],
        "tools": ToolSet(allowed_tool_ids=["fs.read"]),
        "autonomy": AutonomyConfig(level=2),
    }
    kwargs.update(overrides)
    return Agent(**kwargs)


def test_status_gate_blocks_non_active_agent() -> None:
    agent = _agent(status=AgentStatus.INACTIVE)
    with pytest.raises(AgentNotExecutableError):
        check_status(agent)


def test_status_gate_passes_active_agent() -> None:
    check_status(_agent())


def test_capability_gate_allows_matching() -> None:
    check_capability(_agent(), "development.backend")


def test_capability_gate_blocks_missing() -> None:
    with pytest.raises(PermissionDeniedError):
        check_capability(_agent(), "quality.assurance")


def test_capability_gate_skipped_when_not_required() -> None:
    check_capability(_agent(), None)


def test_permission_gate_allows_granted_tool() -> None:
    check_permissions(_agent(), ["fs.read"])


def test_permission_gate_blocks_ungranted_tool() -> None:
    with pytest.raises(PermissionDeniedError):
        check_permissions(_agent(), ["fs.write"])


def test_permission_gate_default_deny_when_no_toolset() -> None:
    agent = _agent(tools=None)
    with pytest.raises(PermissionDeniedError):
        check_permissions(agent, ["fs.read"])


def test_autonomy_allowed_when_level_sufficient() -> None:
    decision = check_autonomy(_agent(), 2)
    assert decision is AutonomyDecision.ALLOWED


def test_autonomy_approval_required_when_exceeding_level() -> None:
    decision = check_autonomy(_agent(), 3)
    assert decision is AutonomyDecision.APPROVAL_REQUIRED


def test_autonomy_defaults_to_zero_without_config() -> None:
    decision = check_autonomy(_agent(autonomy=None), 1)
    assert decision is AutonomyDecision.APPROVAL_REQUIRED


def test_input_size_accepts_small_input() -> None:
    limits = ExecutionLimits(max_input_chars=100)
    out = validate_input_size("hello", limits)
    assert out == "hello"


def test_input_size_truncates_to_preview() -> None:
    limits = ExecutionLimits(inline_preview_chars=8, max_input_chars=100)
    out = validate_input_size("A" * 40, limits)
    assert out.endswith("[truncated]")
    assert len(out) < 40


def test_input_size_rejects_oversized_input() -> None:
    limits = ExecutionLimits(inline_preview_chars=8, max_input_chars=20)
    with pytest.raises(PayloadTooLargeError):
        validate_input_size("B" * 30, limits)


def test_build_context_populates_fields() -> None:
    request = RuntimeRequest(
        agent_handle="test-agent",
        input="Do the thing",
        project_id="proj",
        task_id="task",
        correlation_id="corr-1",
        required_capability="development.backend",
    )
    context = build_context(
        _agent(),
        request,
        project_state={"id": "proj", "name": "P"},
        limits=ExecutionLimits(),
    )
    assert context.agent_id == "test_agent"
    assert context.project_id == "proj"
    assert context.task_id == "task"
    assert context.correlation_id == "corr-1"
    assert context.autonomy_level == 2
    assert "project" in context.relevant_context
    assert context.limits.inline_preview_chars == 4000


def test_build_context_marks_truncated_input() -> None:
    request = RuntimeRequest(agent_handle="test-agent", input="X" * 60)
    limits = ExecutionLimits(inline_preview_chars=10, max_input_chars=200)
    context = build_context(_agent(), request, limits=limits)
    assert context.input_truncated is True
