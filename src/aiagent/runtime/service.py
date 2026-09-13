"""Agent runtime service: orchestrate a single agent run (docs/plan/37, STEP 5).

Responsibilities (from the STEP 5 requirements):

* resolve the agent definition and apply the pre-run gates
  (status / capability / tool permissions / autonomy - see
  :mod:`aiagent.runtime.context`),
* validate the execution context (project / task references) and input size,
* prepare the versioned instruction payload (:mod:`aiagent.runtime.prompts`),
* resolve the model configuration and perform the model call through the
  :class:`aiagent.runtime.gateway.ModelGateway` (no provider coupling here),
* capture output, usage, and duration; persist an :class:`AgentRun`,
* run the state machine ``CREATED -> ... -> SUCCEEDED | FAILED | CANCELLED``
  with retry/backoff for retryable provider failures (docs/plan/06 §3),
* honour the caller's cooperative cancellation token,
* emit domain events + audit entries, keeping every persisted error sealed
  (no secrets, no raw payloads in events or documents).

The service executes **no tools** and is provider-independent; the task /
workflow engines consume its results in later steps.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiagent.core.config import RuntimeSettings
from aiagent.core.errors import (
    AiAgentError,
    InvalidExecutionContextError,
    NotFoundError,
    PayloadTooLargeError,
)
from aiagent.core.logging import get_logger
from aiagent.db.base import utcnow
from aiagent.db.constants import AgentRunStatus
from aiagent.db.models import Agent, AgentRun, RetryPolicy
from aiagent.db.repositories import Repositories
from aiagent.events.audit import AuditLogger, snapshot
from aiagent.events.publisher import EventPublisher
from aiagent.events.types import DomainEvent, EventType
from aiagent.runtime import content as content_mod
from aiagent.runtime import prompts as prompts_mod
from aiagent.runtime import retry as retry_mod
from aiagent.runtime import run_state
from aiagent.runtime.context import (
    AutonomyDecision,
    ExecutionContext,
    ExecutionLimits,
    RuntimeRequest,
    build_context,
    check_autonomy,
    check_capability,
    check_permissions,
    check_status,
)
from aiagent.runtime.errors import (
    ModelConfigurationError,
    ProviderCancelledError,
    is_retryable,
)
from aiagent.runtime.gateway import ModelGateway
from aiagent.runtime.models import CancelToken, ModelRequest, ModelResponse

logger = get_logger("runtime")

_STATUS_EVENTS: dict[AgentRunStatus, EventType] = {
    AgentRunStatus.CREATED: EventType.AGENT_RUN_CREATED,
    AgentRunStatus.READY: EventType.AGENT_RUN_READY,
    AgentRunStatus.CLAIMED: EventType.AGENT_RUN_CLAIMED,
    AgentRunStatus.RUNNING: EventType.AGENT_RUN_STARTED,
    AgentRunStatus.PAUSED: EventType.AGENT_RUN_PAUSED,
    AgentRunStatus.SUCCEEDED: EventType.AGENT_RUN_SUCCEEDED,
    AgentRunStatus.FAILED: EventType.AGENT_RUN_FAILED,
    AgentRunStatus.CANCELLED: EventType.AGENT_RUN_CANCELLED,
}


@dataclass(frozen=True)
class RuntimeOutcome:
    """Result of a run, already persisted (the run row is the source of truth)."""

    run: AgentRun
    decision: AutonomyDecision
    result: str | None = None
    output_ref: str | None = None
    error_code: str | None = None
    error_detail: dict[str, Any] | None = None


@dataclass(frozen=True)
class _ModelPlan:
    provider: str
    model: str
    max_tokens: int
    temperature: float | None
    timeout_secs: float
    retry_policy: RetryPolicy


class AgentRuntimeService:
    """Execute one agent definition against the configured model gateway."""

    def __init__(
        self,
        *,
        repos: Repositories,
        publisher: EventPublisher,
        audit: AuditLogger,
        gateway: ModelGateway,
        instructions: prompts_mod.InstructionSource,
        content_store: content_mod.ContentStore,
        settings: RuntimeSettings | None = None,
    ) -> None:
        self._repos = repos
        self._publisher = publisher
        self._audit = audit
        self._gateway = gateway
        self._instructions = instructions
        self._content = content_store
        self._settings = settings or RuntimeSettings()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        request: RuntimeRequest,
        *,
        cancel_token: CancelToken | None = None,
    ) -> RuntimeOutcome:
        """Execute one run of the requested agent against the gateway."""
        agent = await self._resolve_agent(request.agent_handle)

        check_status(agent)
        check_capability(agent, request.required_capability)
        check_permissions(agent, request.requested_tool_ids)
        decision = check_autonomy(agent, request.required_autonomy_level)

        limits = self._build_limits(request, agent)
        if len(request.input) > limits.max_input_chars:
            raise PayloadTooLargeError(
                f"input {len(request.input):,} chars exceeds limit {limits.max_input_chars:,}"
            )

        project_state, task_state = await self._load_references(request)
        context = build_context(
            agent,
            request,
            project_state=project_state,
            task_state=task_state,
            limits=limits,
        )

        attempt = await self._repos.agent_runs.next_attempt(agent.agent_id, request.task_id)
        run = self._new_run(agent, request, context, attempt=attempt)

        if decision is AutonomyDecision.APPROVAL_REQUIRED:
            await self._create_run(run)
            await self._transition_to(run, AgentRunStatus.READY)
            run = await self._transition_to(run, AgentRunStatus.PAUSED)
            logger.info(
                "agent run paused awaiting approval",
                extra={"run_id": run.id, "agent_id": agent.agent_id},
            )
            return RuntimeOutcome(run=run, decision=decision)

        # Resolve model config *before* creating the run so configuration errors
        # never leave an orphaned CREATED run behind.
        model_plan = self._resolve_model_plan(agent)
        await self._create_run(run)
        run = await self._transition_to(run, AgentRunStatus.READY)
        run = await self._transition_to(run, AgentRunStatus.CLAIMED)
        run = await self._transition_to(run, AgentRunStatus.RUNNING)

        await self._store_input(run, request.input, context.limits)

        return await self._execute_with_retry(
            run, agent, context, model_plan, cancel_token=cancel_token
        )

    # ------------------------------------------------------------------
    # Resolution + context loading
    # ------------------------------------------------------------------

    async def _resolve_agent(self, handle: str) -> Agent:
        agent = await self._repos.agents.find_by_slug(handle)
        if agent is None:
            agent = await self._repos.agents.find_by_agent_id(handle)
        if agent is None:
            raise NotFoundError(f"agent {handle!r} not found")
        return agent

    async def find_run(self, run_id: str) -> AgentRun | None:
        """Observability/support helper: fetch a persisted run by id."""
        return await self._repos.agent_runs.find_by_id(run_id)

    async def _load_references(
        self, request: RuntimeRequest
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        project_state: dict[str, Any] | None = None
        task_state: dict[str, Any] | None = None
        if request.project_id is not None:
            project = await self._repos.projects.find_by_id(request.project_id)
            if project is None:
                raise InvalidExecutionContextError(f"project {request.project_id!r} not found")
            project_state = {
                "id": project.id,
                "name": project.name,
                "stage": project.stage.value,
                "status": project.status.value,
            }
        if request.task_id is not None:
            task = await self._repos.tasks.find_by_id(request.task_id)
            if task is None:
                raise InvalidExecutionContextError(f"task {request.task_id!r} not found")
            task_state = {"id": task.id, "title": task.title, "status": task.status.value}
        return project_state, task_state

    def _build_limits(self, request: RuntimeRequest, agent: Agent) -> ExecutionLimits:
        return ExecutionLimits(
            max_input_chars=self._settings.max_input_chars,
            max_output_chars=self._settings.max_output_chars,
            inline_preview_chars=self._settings.inline_preview_chars,
            max_tokens=request.max_tokens or self._settings.default_max_tokens,
            timeout_secs=self._settings.default_timeout_secs,
        )

    def _resolve_model_plan(self, agent: Agent) -> _ModelPlan:
        """Resolve the provider / model / timeout / retry policy for this agent."""
        settings = self._settings
        cfg = agent.model
        provider = cfg.provider.value if (cfg and cfg.provider) else settings.default_provider
        model = cfg.model if (cfg and cfg.model) else settings.default_model
        if not model:
            raise ModelConfigurationError("model configuration incomplete (no model id)")
        if not self._gateway.supports(provider):
            raise ModelConfigurationError(f"provider {provider!r} is not configured")

        policy = RetryPolicy(
            max_attempts=settings.retry.max_attempts,
            backoff_base_secs=settings.retry.backoff_base_secs,
            backoff_cap_secs=settings.retry.backoff_cap_secs,
            jitter=settings.retry.jitter,
        )
        if cfg and cfg.retry_policy:
            policy = cfg.retry_policy
        max_tokens = cfg.max_tokens if (cfg and cfg.max_tokens) else settings.default_max_tokens
        timeout = cfg.timeout_secs if (cfg and cfg.timeout_secs) else settings.default_timeout_secs
        temperature = cfg.temperature if cfg else None
        return _ModelPlan(
            provider=provider,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_secs=timeout,
            retry_policy=policy,
        )

    # ------------------------------------------------------------------
    # Persistence + events
    # ------------------------------------------------------------------

    def _new_run(
        self, agent: Agent, request: RuntimeRequest, context: ExecutionContext, *, attempt: int
    ) -> AgentRun:
        return AgentRun(
            agent_id=agent.agent_id,
            agent_version=agent.version,
            task_id=request.task_id,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id,
            attempt=attempt,
            status=AgentRunStatus.CREATED,
            correlation_id=request.correlation_id,
            input=context.input[: context.limits.inline_preview_chars],
        )

    async def _create_run(self, run: AgentRun) -> None:
        await self._repos.agent_runs.create(run)
        await self._publish_agent_run(run)
        await self._audit.record(
            action="agent_run.create",
            project_id=run.project_id,
            resource_type="agent_run",
            resource_id=run.id,
            after=snapshot(run),
        )

    async def _transition_to(
        self,
        run: AgentRun,
        status: AgentRunStatus,
        *,
        extra_changes: dict[str, Any] | None = None,
    ) -> AgentRun:
        """Validate + apply a state transition, emit its event, and re-read the row.

        ``extra_changes`` carries fields that changed alongside the transition
        (usage metrics, error detail, previews); they are persisted in the same
        ``$set`` so the returned document is always authoritative.
        """
        run_state.assert_run_transition(run.status, status)
        changes: dict[str, Any] = {"status": status.value}
        run.status = status

        if status is AgentRunStatus.RUNNING and run.started_at is None:
            run.started_at = utcnow()
            changes["started_at"] = run.started_at
        if status in run_state.TERMINAL_STATES or status is AgentRunStatus.FAILED:
            run.completed_at = utcnow()
            changes["completed_at"] = run.completed_at
        if extra_changes:
            changes.update(extra_changes)

        updated = await self._repos.agent_runs.update(run.id, changes)
        if updated is None:
            raise NotFoundError(f"agent run {run.id} not found")

        await self._publish_agent_run(updated)
        await self._audit.record(
            action=f"agent_run.{status.value}",
            project_id=updated.project_id,
            resource_type="agent_run",
            resource_id=updated.id,
            before=snapshot(run),
            after=snapshot(updated),
        )
        return updated

    async def _publish_agent_run(self, run: AgentRun) -> None:
        event_type = _STATUS_EVENTS.get(run.status)
        if event_type is None:
            return
        await self._publisher.publish(
            DomainEvent.build(
                event_type,
                payload={
                    "run_id": run.id,
                    "agent_id": run.agent_id,
                    "attempt": run.attempt,
                    "status": run.status.value,
                },
                project_id=run.project_id,
                emitted_by="service:runtime",
            )
        )

    # ------------------------------------------------------------------
    # Content persistence (preview + artifact references)
    # ------------------------------------------------------------------

    async def _store_input(self, run: AgentRun, raw_input: str, limits: ExecutionLimits) -> None:
        if len(raw_input) > limits.inline_preview_chars:
            ref = self._content.store(
                content_mod.KIND_INPUT,
                run.id,
                raw_input,
                max_preview_chars=limits.inline_preview_chars,
            )
            run.input_ref = ref.uri
            run.input = ref.preview
            await self._repos.agent_runs.update(
                run.id, {"input_ref": ref.uri, "input": ref.preview}
            )

    def _store_output(self, run: AgentRun, content: str, limits: ExecutionLimits) -> None:
        if len(content) <= limits.inline_preview_chars:
            run.output = content
            run.output_truncated = False
            return
        ref = self._content.store(
            content_mod.KIND_OUTPUT,
            run.id,
            content,
            max_preview_chars=limits.inline_preview_chars,
        )
        run.output_ref = ref.uri
        run.output = ref.preview
        run.output_truncated = ref.truncated

    # ------------------------------------------------------------------
    # Execution loop (state machine + retry + cancellation)
    # ------------------------------------------------------------------

    async def _execute_with_retry(
        self,
        run: AgentRun,
        agent: Agent,
        context: ExecutionContext,
        plan: _ModelPlan,
        *,
        cancel_token: CancelToken | None,
    ) -> RuntimeOutcome:
        system_prompt = self._build_system_prompt(agent, context)
        user_prompt = self._build_user_prompt(context)
        retry_count = 0

        while True:
            request = ModelRequest(
                model_id=plan.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=plan.max_tokens,
                temperature=plan.temperature,
            )
            try:
                response = await self._gateway.complete(
                    provider=plan.provider,
                    request=request,
                    cancel_token=cancel_token,
                    timeout_secs=plan.timeout_secs,
                )
                return await self._finalize_success(run, context, response, retry_count)
            except ProviderCancelledError as exc:
                return await self._finalize_cancelled(run, exc)
            except asyncio.CancelledError:
                return await self._finalize_cancelled(run, ProviderCancelledError("run cancelled"))
            except Exception as exc:  # noqa: BLE001 - classified below
                retryable = is_retryable(exc)
                if (
                    not retryable
                    or retry_count + 1 >= plan.retry_policy.max_attempts
                    or (cancel_token is not None and cancel_token.is_set)
                ):
                    return await self._finalize_failed(run, exc, retry_count=retry_count)

                retry_count += 1
                await self._transition_to(
                    run,
                    AgentRunStatus.FAILED,
                    extra_changes={
                        "retry_count": retry_count,
                        "error_code": _error_code(exc),
                        "error_detail": _error_detail(exc),
                    },
                )
                delay = retry_mod.compute_backoff(plan.retry_policy, retry_count + 1)
                if not await self._sleep_backoff(delay, cancel_token=cancel_token):
                    return await self._finalize_cancelled(
                        run, ProviderCancelledError("cancelled during retry backoff")
                    )
                run = await self._transition_to(run, AgentRunStatus.READY)
                run = await self._transition_to(run, AgentRunStatus.CLAIMED)
                run = await self._transition_to(run, AgentRunStatus.RUNNING)
                continue

    async def _finalize_success(
        self,
        run: AgentRun,
        context: ExecutionContext,
        response: ModelResponse,
        retry_count: int,
    ) -> RuntimeOutcome:
        self._store_output(run, response.content, context.limits)
        run.provider = response.provider
        run.model = response.model_id
        run.tokens_in = response.usage.tokens_in
        run.tokens_out = response.usage.tokens_out
        run.retry_count = retry_count
        run.duration_ms = _duration_ms(run.started_at)

        run = await self._transition_to(
            run,
            AgentRunStatus.VALIDATING,
            extra_changes={
                "provider": run.provider,
                "model": run.model,
                "tokens_in": run.tokens_in,
                "tokens_out": run.tokens_out,
                "duration_ms": run.duration_ms,
                "retry_count": run.retry_count,
                "output": run.output,
                "output_ref": run.output_ref,
                "output_truncated": run.output_truncated,
            },
        )
        run = await self._transition_to(run, AgentRunStatus.SUCCEEDED)

        logger.info(
            "agent run succeeded",
            extra={
                "run_id": run.id,
                "agent_id": run.agent_id,
                "provider": run.provider,
                "model": run.model,
                "tokens_in": run.tokens_in,
                "tokens_out": run.tokens_out,
                "duration_ms": run.duration_ms,
            },
        )
        return RuntimeOutcome(
            run=run,
            decision=AutonomyDecision.ALLOWED,
            result=run.output,
            output_ref=run.output_ref,
        )

    async def _finalize_failed(
        self, run: AgentRun, exc: BaseException, *, retry_count: int
    ) -> RuntimeOutcome:
        run.retry_count = retry_count
        run = await self._transition_to(
            run,
            AgentRunStatus.FAILED,
            extra_changes={
                "retry_count": retry_count,
                "error_code": _error_code(exc),
                "error_detail": _error_detail(exc),
            },
        )
        logger.warning("agent run failed", extra={"run_id": run.id, "reason": _error_code(exc)})
        return RuntimeOutcome(
            run=run,
            decision=AutonomyDecision.ALLOWED,
            error_code=run.error_code,
            error_detail=run.error_detail,
        )

    async def _finalize_cancelled(
        self, run: AgentRun, exc: ProviderCancelledError
    ) -> RuntimeOutcome:
        run = await self._transition_to(
            run,
            AgentRunStatus.CANCELLED,
            extra_changes={"error_code": exc.error_code, "error_detail": _error_detail(exc)},
        )
        logger.warning("agent run cancelled", extra={"run_id": run.id})
        return RuntimeOutcome(
            run=run,
            decision=AutonomyDecision.ALLOWED,
            error_code=run.error_code,
            error_detail=run.error_detail,
        )

    def _build_system_prompt(self, agent: Agent, context: ExecutionContext) -> str:
        allowed_tools = []
        if agent.tools:
            allowed_tools = sorted(agent.tools.allowed_tool_ids)
        return prompts_mod.build_system_prompt(
            agent_identity=agent.name,
            agent_description=agent.description,
            system_instructions=self._instructions.system_instructions(agent.system_prompt_ref),
            context=context,
            allowed_tool_ids=allowed_tools,
        )

    def _build_user_prompt(self, context: ExecutionContext) -> str:
        project_summary = context.relevant_context.get("project")
        task_summary = context.relevant_context.get("task")
        return prompts_mod.build_user_prompt(
            context=context,
            project_summary=json.dumps(project_summary) if project_summary else None,
            task_summary=json.dumps(task_summary) if task_summary else None,
        )

    @staticmethod
    async def _sleep_backoff(seconds: float, *, cancel_token: CancelToken | None) -> bool:
        """Sleep for *seconds*; return False when the caller cancelled meanwhile."""
        if seconds <= 0:
            return not (cancel_token is not None and cancel_token.is_set)
        if cancel_token is None:
            await asyncio.sleep(seconds)
            return True
        try:
            await asyncio.wait_for(cancel_token.wait(), timeout=seconds)
        except TimeoutError:
            return True
        return False


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, AiAgentError):
        return exc.error_code
    return "runtime_error"


def _error_detail(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, AiAgentError):
        return {"type": type(exc).__name__, "message": exc.message}
    return {"type": type(exc).__name__, "message": "unexpected runtime failure"}


def _duration_ms(started_at: datetime | None) -> int | None:
    if started_at is None:
        return None
    return max(0, int((utcnow() - started_at).total_seconds() * 1000))
