"""Internal agent runtime API (STEP 5).

Endpoints:

* ``POST /internal/agents/{handle}/run`` - execute one agent run against the
  configured model gateway (mock provider in STEP 5).  Returns the persisted
  :class:`AgentRun` summary; no tools are executed and no tasks are scheduled.
* ``GET /internal/agent-runs/{run_id}`` - observability: fetch a persisted run.

Security posture (docs/plan/31 §2): this router is *internal*.  Operation is
still governed by the runtime gates - the agent must be active, the requested
capability and tool permissions must be granted, and the autonomy level must
permit execution - and both input and output are size-limited by the runtime.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from aiagent.api.deps import ServicesDep
from aiagent.api.envelope import ok
from aiagent.core.errors import NotFoundError
from aiagent.db.models import AgentRun
from aiagent.runtime.context import RuntimeRequest

router = APIRouter(prefix="/internal", tags=["internal-runtime"])


class RunAgentRequest(BaseModel):
    """Payload for POST /internal/agents/{handle}/run."""

    model_config = ConfigDict(extra="forbid")

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


def _run_payload(run: AgentRun) -> dict[str, Any]:
    """Summarize a run for API consumers (previews only, never full content)."""
    return {
        "run_id": run.id,
        "agent_id": run.agent_id,
        "attempt": run.attempt,
        "status": run.status.value,
        "provider": run.provider,
        "model": run.model,
        "tokens_in": run.tokens_in,
        "tokens_out": run.tokens_out,
        "duration_ms": run.duration_ms,
        "retry_count": run.retry_count,
        "correlation_id": run.correlation_id,
        "output": run.output,
        "output_ref": run.output_ref,
        "output_truncated": run.output_truncated,
        "error_code": run.error_code,
        "error_detail": run.error_detail,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.post("/agents/{handle}/run", summary="Execute one agent run (internal)")
async def run_agent(handle: str, payload: RunAgentRequest, services: ServicesDep) -> dict:
    request = RuntimeRequest(agent_handle=handle, **payload.model_dump())
    outcome = await services.runtime.run(request)
    data = _run_payload(outcome.run)
    data["decision"] = outcome.decision.value
    if outcome.output_ref:
        data["output_ref"] = outcome.output_ref
    return ok(data=data)


@router.get("/agent-runs/{run_id}", summary="Fetch a persisted agent run (internal)")
async def get_run(run_id: str, services: ServicesDep) -> dict:
    run = await services.runtime.find_run(run_id)
    if run is None:
        raise NotFoundError(f"agent run {run_id} not found")
    return ok(data=_run_payload(run))
