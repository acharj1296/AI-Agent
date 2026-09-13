"""AgentRun state machine (docs/plan/37, STEP 5 runtime)."""

from __future__ import annotations

import pytest

from aiagent.core.errors import InvalidStateError
from aiagent.db.constants import AgentRunStatus
from aiagent.runtime.run_state import (
    TERMINAL_STATES,
    allows,
    assert_run_transition,
)

R = AgentRunStatus


def _pairs() -> list[tuple[AgentRunStatus, AgentRunStatus]]:
    pairs: list[tuple[AgentRunStatus, AgentRunStatus]] = []
    for source in R:
        for target in R:
            pairs.append((source, target))
    return pairs


def test_canonical_pipeline_transitions_allowed() -> None:
    assert allows(R.CREATED, R.READY)
    assert allows(R.READY, R.CLAIMED)
    assert allows(R.CLAIMED, R.RUNNING)
    assert allows(R.RUNNING, R.VALIDATING)
    assert allows(R.VALIDATING, R.SUCCEEDED)


def test_canonical_failure_and_retry_edges_allowed() -> None:
    assert allows(R.RUNNING, R.FAILED)
    assert allows(R.FAILED, R.READY)  # retry edge (STEP 5)
    assert allows(R.FAILED, R.ESCALATED)
    assert allows(R.ESCALATED, R.READY)
    assert allows(R.READY, R.PAUSED)  # approval-required gate (STEP 5 extension)
    assert allows(R.PAUSED, R.RUNNING)


def test_cancellation_edges_allowed() -> None:
    for source in (R.CREATED, R.READY, R.CLAIMED, R.RUNNING, R.FAILED, R.PAUSED, R.ESCALATED):
        assert allows(source, R.CANCELLED)


def test_terminal_states_are_terminal() -> None:
    assert R.SUCCEEDED in TERMINAL_STATES
    assert R.CANCELLED in TERMINAL_STATES
    assert not allows(R.SUCCEEDED, R.READY)
    assert not allows(R.CANCELLED, R.READY)
    assert not allows(R.SUCCEEDED, R.SUCCEEDED)


def test_invalid_pipeline_transitions_rejected() -> None:
    assert not allows(R.CREATED, R.RUNNING)
    assert not allows(R.CREATED, R.SUCCEEDED)
    assert not allows(R.READY, R.RUNNING)
    assert not allows(R.CLAIMED, R.SUCCEEDED)
    assert not allows(R.RUNNING, R.READY)
    assert not allows(R.VALIDATING, R.RUNNING)
    assert not allows(R.PAUSED, R.SUCCEEDED)


def test_assert_raises_on_invalid_transition() -> None:
    with pytest.raises(InvalidStateError):
        assert_run_transition(R.CREATED, R.SUCCEEDED)


def test_full_matrix_is_symmetric_with_allows() -> None:
    for source, target in _pairs():
        if allows(source, target):
            assert_run_transition(source, target)  # must not raise
