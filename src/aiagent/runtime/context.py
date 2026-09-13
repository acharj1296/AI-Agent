"""Execution context + pre-run gates (permission, autonomy, capability) (STEP 5).

The :class:`RuntimeRequest` is the caller-supplied run trigger; the context is
the *resolved* request enriched with the agent definition, validated references,
model config, and limit defaults.  The runtime never persists the context itself
- only the :class:`AgentRun` reflects what was used.

Gates run in order: status -> capability -> tool permissions -> autonomy.
Failing at any gate aborts the run (no :class:`AgentRun` is persisted); approval-
required autonomy pauses the run and returns an outcome without a model call.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aiagent.core.errors import (
    AgentNotExecutableError,
    PayloadTooLargeError,
    PermissionDeniedError,
)
from aiagent.db.constants import AgentStatus, ToolPermissionLevel
from aiagent.db.models import Agent


class AutonomyDecision(StrEnum):
    ALLOWED = "allowed"
    APPROVAL_REQUIRED = "approval_required"


class ExecutionLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_input_chars: int = 200_000
    max_output_chars: int = 100_000
    inline_preview_chars: int = 4_000
    max_tokens: int = 1024
    timeout_secs: float = 30.0


class RuntimeRequest(BaseModel):
    """Input payload for a run (validated at the API / service boundary)."""

    model_config = ConfigDict(extra="forbid")
    agent_handle: str = Field(..., min_length=1, max_length=256)
    input: str = Field(..., min_length=1, max_length=2_000_000)
    project_id: str | None = None
    task_id: str | None = None
    workflow_run_id: str | None = None
    correlation_id: str | None = None
    required_capability: str | None = None
    required_autonomy_level: int = Field(default=0, ge=0, le=5)
    requested_tool_ids: list[str] = Field(default_factory=list)
    input_context: dict[str, Any] = Field(default_factory=dict)
    request_metadata: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int | None = Field(default=None, ge=1)


class ExecutionContext(BaseModel):
    """Resolved runtime state assembled before the model call (not persisted)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    agent_id: str
    agent_version: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    workflow_run_id: str | None = None
    correlation_id: str | None = None
    input: str = ""
    relevant_context: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    permissions: dict[str, Any] | None = None
    autonomy_level: int = 0
    model: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    limits: ExecutionLimits = Field(default_factory=ExecutionLimits)
    input_truncated: bool = False


# ----- Gates ----------------------------------------------------------------


def check_status(agent: Agent) -> None:
    if agent.status is not AgentStatus.ACTIVE:
        raise AgentNotExecutableError(
            f"agent {agent.agent_id!r} is not active (status={agent.status.value})"
        )


def check_capability(agent: Agent, required: str | None) -> None:
    if required and not agent.has_capability(required):
        raise PermissionDeniedError(f"agent {agent.agent_id!r} lacks capability {required!r}")


def check_permissions(agent: Agent, requested_tool_ids: list[str]) -> None:
    for tool_id in requested_tool_ids:
        if not agent.can_use_tool(tool_id, level=ToolPermissionLevel.READ):
            raise PermissionDeniedError(
                f"agent {agent.agent_id!r} does not have read access to tool {tool_id!r}"
            )


def check_autonomy(agent: Agent, required_level: int) -> AutonomyDecision:
    level = agent.autonomy.level if agent.autonomy else 0
    if required_level <= level:
        return AutonomyDecision.ALLOWED
    return AutonomyDecision.APPROVAL_REQUIRED


def validate_input_size(raw_input: str, limits: ExecutionLimits) -> str:
    """Validate input size and truncate to preview if needed (keeps model payload small)."""
    if len(raw_input) > limits.max_input_chars:
        raise PayloadTooLargeError(
            f"input {len(raw_input):,} chars exceeds limit {limits.max_input_chars:,}"
        )
    if len(raw_input) > limits.inline_preview_chars:
        return raw_input[: limits.inline_preview_chars] + "\n[truncated]"
    return raw_input


def build_context(
    agent: Agent,
    request: RuntimeRequest,
    *,
    project_state: dict[str, Any] | None = None,
    task_state: dict[str, Any] | None = None,
    limits: ExecutionLimits | None = None,
) -> ExecutionContext:
    """Assemble the resolved execution context (used for instruction building + audit)."""
    limits = limits or ExecutionLimits()
    input_preview = validate_input_size(request.input, limits)
    relevant: dict[str, Any] = dict(request.input_context)
    if project_state:
        relevant["project"] = project_state
    if task_state:
        relevant["task"] = task_state
    return ExecutionContext(
        agent_id=agent.agent_id,
        agent_version=agent.version,
        project_id=request.project_id,
        task_id=request.task_id,
        workflow_run_id=request.workflow_run_id,
        correlation_id=request.correlation_id,
        input=request.input,
        relevant_context=relevant,
        capabilities=[c.value for c in agent.capabilities],
        permissions=agent.permissions.model_dump() if agent.permissions else None,
        autonomy_level=agent.autonomy.level if agent.autonomy else 0,
        model=agent.model.model_dump() if agent.model else None,
        metadata=dict(request.request_metadata),
        limits=limits,
        input_truncated=len(input_preview) < len(request.input),
    )
