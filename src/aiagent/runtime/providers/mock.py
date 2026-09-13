"""Deterministic mock model provider (docs/plan/49 Phase 2; STEP 5).

Used by default configuration (``runtime.default_provider: mock``) so the
entire runtime - context, retries, cancellation, persistence - is verified
without external credentials.  Real provider adapters (openai/anthropic/...)
are a later phase.

Behavior is scriptable per call via :meth:`DeterministicMockModelProvider.
script`; after the script is exhausted the ``default_behavior`` repeats.
Output and token counts are deterministic functions of the input so tests can
assert on them exactly.
"""

from __future__ import annotations

import asyncio
from enum import StrEnum

from aiagent.runtime.errors import (
    ProviderCancelledError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    TransientProviderError,
)
from aiagent.runtime.models import CancelToken, ModelRequest, ModelResponse, ModelUsage


class ScriptedBehavior(StrEnum):
    """Deterministic behaviors a scripted mock call performs."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    TRANSIENT = "transient"
    INVALID = "invalid_response"
    CANCELLED = "cancelled"


_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


class DeterministicMockModelProvider:
    """A :class:`aiagent.runtime.models.ModelProvider` with scripted behavior."""

    name = "mock"

    def __init__(
        self,
        *,
        tick_secs: float = 0.0,
        default_behavior: ScriptedBehavior = ScriptedBehavior.SUCCESS,
    ) -> None:
        self._tick_secs = tick_secs
        self._default_behavior = default_behavior
        self._script: list[ScriptedBehavior] = []

    @property
    def default_model(self) -> str:
        return "mock-default"

    def script(self, behaviors: list[ScriptedBehavior]) -> None:
        """Queue behaviors; each ``complete`` consumes one, reset per instance."""
        self._script = list(behaviors)

    def _next_behavior(self) -> ScriptedBehavior:
        if not self._script:
            return self._default_behavior
        return self._script.pop(0)

    async def _tick(self, cancel_token: CancelToken | None) -> None:
        if cancel_token is not None and cancel_token.is_set:
            raise ProviderCancelledError("cancelled before mock call")
        if self._tick_secs > 0:
            await asyncio.sleep(self._tick_secs)
            if cancel_token is not None and cancel_token.is_set:
                raise ProviderCancelledError("cancelled during mock call")

    async def complete(
        self, request: ModelRequest, *, cancel_token: CancelToken | None = None
    ) -> ModelResponse:
        await self._tick(cancel_token)
        behavior = self._next_behavior()

        if behavior is ScriptedBehavior.TIMEOUT:
            raise TimeoutError("mock provider timed out")
        if behavior is ScriptedBehavior.RATE_LIMIT:
            raise ProviderRateLimitError("mock provider rate limited")
        if behavior is ScriptedBehavior.SERVER_ERROR:
            raise ProviderUnavailableError("mock provider returned 5xx")
        if behavior is ScriptedBehavior.TRANSIENT:
            raise TransientProviderError("mock provider transient network error")
        if behavior is ScriptedBehavior.CANCELLED:
            raise ProviderCancelledError("mock provider cancelled")
        if behavior is ScriptedBehavior.INVALID:
            return ModelResponse(
                content="",
                usage=ModelUsage(tokens_in=4, tokens_out=0),
                provider=self.name,
                model_id=request.model_id,
            )

        content = self._success_content(request)
        return ModelResponse(
            content=content,
            usage=ModelUsage(
                tokens_in=_estimate_tokens(request.system_prompt + request.user_prompt),
                tokens_out=_estimate_tokens(content),
            ),
            provider=self.name,
            model_id=request.model_id,
        )

    @staticmethod
    def _success_content(request: ModelRequest) -> str:
        prompt_head = request.user_prompt.strip().replace("\n", " ")[:200]
        return f"[mock:model={request.model_id}] {prompt_head} -> ok"
