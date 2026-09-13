"""AgentRun state machine (docs/plan/37; STEP 5).

Canonical transitions (plan 37), plus one documented STEP 5 extension:
``READY -> PAUSED`` allows the runtime to park a run awaiting human approval
before it is ever claimed (approval-required autonomy decisions).  ``FAILED ->
READY`` is the retry edge used by the runtime retry loop; ``FAILED ->
ESCALATED`` exists for a future orchestrator that escalates exhausted runs.

``SUCCEEDED`` and ``CANCELLED`` are terminal.
"""

from __future__ import annotations

from aiagent.core.errors import InvalidStateError
from aiagent.db.constants import AgentRunStatus

SUCCEEDED = AgentRunStatus.SUCCEEDED
CANCELLED = AgentRunStatus.CANCELLED

_TRANSITIONS: dict[AgentRunStatus, frozenset[AgentRunStatus]] = {
    AgentRunStatus.CREATED: frozenset({AgentRunStatus.READY, AgentRunStatus.CANCELLED}),
    AgentRunStatus.READY: frozenset(
        {AgentRunStatus.CLAIMED, AgentRunStatus.PAUSED, AgentRunStatus.CANCELLED}
    ),
    AgentRunStatus.CLAIMED: frozenset(
        {AgentRunStatus.RUNNING, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED}
    ),
    AgentRunStatus.RUNNING: frozenset(
        {
            AgentRunStatus.VALIDATING,
            AgentRunStatus.FAILED,
            AgentRunStatus.PAUSED,
            AgentRunStatus.CANCELLED,
        }
    ),
    AgentRunStatus.VALIDATING: frozenset(
        {AgentRunStatus.SUCCEEDED, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED}
    ),
    AgentRunStatus.FAILED: frozenset(
        {AgentRunStatus.READY, AgentRunStatus.ESCALATED, AgentRunStatus.CANCELLED}
    ),
    AgentRunStatus.ESCALATED: frozenset({AgentRunStatus.READY, AgentRunStatus.CANCELLED}),
    AgentRunStatus.PAUSED: frozenset({AgentRunStatus.RUNNING, AgentRunStatus.CANCELLED}),
    AgentRunStatus.SUCCEEDED: frozenset(),
    AgentRunStatus.CANCELLED: frozenset(),
}

TERMINAL_STATES: frozenset[AgentRunStatus] = frozenset({SUCCEEDED, CANCELLED})


def allows(current: AgentRunStatus, target: AgentRunStatus) -> bool:
    """True when ``current -> target`` is a permitted AgentRun transition."""
    return target in _TRANSITIONS.get(current, frozenset())


def assert_run_transition(current: AgentRunStatus, target: AgentRunStatus) -> None:
    """Raise :class:`InvalidStateError` when the transition is not permitted."""
    if not allows(current, target):
        raise InvalidStateError(f"invalid agent run transition {current.value} -> {target.value}")
