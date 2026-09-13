"""Agent *definition* registry state machine (docs/plan/04, 05).

This is the lifecycle of an agent definition in the registry, **not** the
``AgentRunStatus`` state machine (docs/plan/06/37) which governs a single
execution.  Allowed transitions are explicit; any other change is rejected so
the registry never records arbitrary status jumps.

    REGISTERED -> ACTIVE
    ACTIVE     -> INACTIVE | DISABLED | DEPRECATED
    INACTIVE   -> ACTIVE | DISABLED | DEPRECATED
    DISABLED   -> ACTIVE | DEPRECATED
    DEPRECATED (terminal)
"""

from __future__ import annotations

from aiagent.core.errors import InvalidStateError
from aiagent.db.constants import AgentStatus

#: Explicit transition table: current state -> set of allowed next states.
AGENT_STATUS_TRANSITIONS: dict[AgentStatus, frozenset[AgentStatus]] = {
    AgentStatus.REGISTERED: frozenset({AgentStatus.ACTIVE}),
    AgentStatus.ACTIVE: frozenset(
        {AgentStatus.INACTIVE, AgentStatus.DISABLED, AgentStatus.DEPRECATED}
    ),
    AgentStatus.INACTIVE: frozenset(
        {AgentStatus.ACTIVE, AgentStatus.DISABLED, AgentStatus.DEPRECATED}
    ),
    AgentStatus.DISABLED: frozenset({AgentStatus.ACTIVE, AgentStatus.DEPRECATED}),
    AgentStatus.DEPRECATED: frozenset(),
}


def assert_transition(current: AgentStatus, next_status: AgentStatus) -> None:
    """Validate a registry status transition; raise when not permitted."""
    allowed = AGENT_STATUS_TRANSITIONS.get(current, frozenset())
    if next_status not in allowed:
        raise InvalidStateError(
            f"agent status transition {current.value} -> {next_status.value} is not allowed"
        )
