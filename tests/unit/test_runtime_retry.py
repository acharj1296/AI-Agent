"""Retry policy / backoff computation for the runtime (docs/plan/06 §3)."""

from __future__ import annotations

import random

from aiagent.db.models import RetryPolicy
from aiagent.runtime.retry import compute_backoff


def test_linear_backoff_without_jitter() -> None:
    policy = RetryPolicy(
        max_attempts=5, backoff_base_secs=1.0, backoff_cap_secs=100.0, jitter=False
    )
    assert compute_backoff(policy, 1) == 1.0
    assert compute_backoff(policy, 2) == 2.0
    assert compute_backoff(policy, 3) == 4.0


def test_backoff_is_capped() -> None:
    policy = RetryPolicy(max_attempts=10, backoff_base_secs=1.0, backoff_cap_secs=5.0, jitter=False)
    assert compute_backoff(policy, 4) == 5.0
    assert compute_backoff(policy, 20) == 5.0


def test_attempt_is_clamped_to_at_least_one() -> None:
    policy = RetryPolicy(max_attempts=3, jitter=False)
    assert compute_backoff(policy, 0) == compute_backoff(policy, 1)


def test_full_jitter_is_bounded_and_seeded_deterministically() -> None:
    policy = RetryPolicy(max_attempts=3, backoff_base_secs=4.0, backoff_cap_secs=16.0, jitter=True)
    first = compute_backoff(policy, 2, rand=random.Random(7))  # noqa: S311
    second = compute_backoff(policy, 2, rand=random.Random(7))  # noqa: S311
    assert first == second
    assert 0.0 < first <= 8.0


def test_default_policy_matches_runtime_default() -> None:
    default = RetryPolicy()
    assert default.max_attempts == 3
    assert default.jitter is True
