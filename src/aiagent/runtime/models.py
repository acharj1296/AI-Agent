"""Provider-independent model abstraction (docs/plan/12, 49 Phase 2).

A :class:`ModelProvider` is the minimal integration point for any model backend
(call or a streaming feed later).  The STEP 5 distribution ships a deterministic
mock provider (:mod:`aiagent.runtime.providers.mock`) so the whole runtime is
exercised end-to-end without external credentials; real provider adapters are a
later phase.

``ModelRequest`` is a frozen dataclass on purpose: it is pure data assembled by
the runtime, never mutated by the provider.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol


class CancelToken:
    """Cooperative cancellation handle passed to providers.

    The runtime owns the token (an :class:`asyncio.Event`); providers check it
    between work steps and raise :class:`aiagent.runtime.errors.
    ProviderCancelledError` when set.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_set(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()


@dataclass(frozen=True)
class ModelRequest:
    """A single model call - system + user text plus generation preferences."""

    model_id: str
    system_prompt: str
    user_prompt: str
    max_tokens: int
    temperature: float | None = None


@dataclass(frozen=True)
class ModelUsage:
    """Token accounting captured from a model call (never raw provider extras)."""

    tokens_in: int
    tokens_out: int

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass(frozen=True)
class ModelResponse:
    """Normalized model output; providers never leak raw shapes to the runtime."""

    content: str
    usage: ModelUsage
    provider: str
    model_id: str


class ModelProvider(Protocol):
    """Implementation contract for model backends.

    ``complete`` must:
    * honour the cooperative ``cancel_token`` between work steps,
    * return a normalized :class:`ModelResponse` on success,
    * raise an :class:`aiagent.runtime.errors` subclass on failure (never raw
      driver exceptions).
    """

    name: str

    @property
    def default_model(self) -> str | None:
        """Model id this provider prefers when the agent does not pin one."""
        ...

    async def complete(
        self, request: ModelRequest, *, cancel_token: CancelToken | None = None
    ) -> ModelResponse: ...
