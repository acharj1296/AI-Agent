"""Retry classification + exponential backoff for model calls (docs/plan/06 §3).

The runtime applies the retry policy from the agent's ``ModelConfig`` (or the
runtime defaults) only to *retryable* errors (see
:func:`aiagent.runtime.errors.is_retryable`).  Attempt numbering: attempt 1 is
the initial call, attempt ``n`` is the first retry.  ``compute_backoff(policy,
n)`` returns the delay *before* starting attempt ``n``.

``jitter`` defaults to true (full jitter) to avoid thundering herds; tests pass
a seeded ``random.Random`` for determinism.
"""

from __future__ import annotations

import random

from aiagent.db.models import RetryPolicy


def compute_backoff(
    policy: RetryPolicy, attempt: int, *, rand: random.Random | None = None
) -> float:
    """Exponential backoff for *attempt* (1-based): base * 2**(attempt-1), capped."""
    attempt = max(1, attempt)
    delay = min(policy.backoff_cap_secs, policy.backoff_base_secs * 2 ** (attempt - 1))
    if not policy.jitter:
        return delay
    source = rand or random
    return source.uniform(0.0, delay)
