"""Deterministic mock model provider (STEP 5 runtime)."""

from __future__ import annotations

import pytest

from aiagent.runtime.errors import (
    ProviderCancelledError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    TransientProviderError,
)
from aiagent.runtime.models import CancelToken, ModelRequest
from aiagent.runtime.providers.mock import DeterministicMockModelProvider, ScriptedBehavior

_REQUEST = ModelRequest(
    model_id="mock-default",
    system_prompt="You are a helper.",
    user_prompt="Implement the auth endpoint.",
    max_tokens=256,
)


@pytest.fixture
def provider() -> DeterministicMockModelProvider:
    return DeterministicMockModelProvider()


async def test_success_returns_deterministic_output(provider) -> None:
    response = await provider.complete(_REQUEST)
    assert response.provider == "mock"
    assert response.model_id == "mock-default"
    assert response.content.startswith("[mock:model=mock-default]")
    assert "auth endpoint" in response.content
    assert response.usage.tokens_in > 0
    assert response.usage.tokens_out > 0
    assert response.usage.total == response.usage.tokens_in + response.usage.tokens_out


async def test_success_echoes_scripted_behaviors(provider) -> None:
    repeated = await provider.complete(_REQUEST)
    provider.script([ScriptedBehavior.SUCCESS, ScriptedBehavior.SUCCESS])
    one = await provider.complete(_REQUEST)
    two = await provider.complete(_REQUEST)
    assert repeated.content == one.content == two.content


async def test_timeout_behavior_raises_timeout(provider) -> None:
    provider.script([ScriptedBehavior.TIMEOUT])
    with pytest.raises(TimeoutError):
        await provider.complete(_REQUEST)


async def test_rate_limit_behavior(provider) -> None:
    provider.script([ScriptedBehavior.RATE_LIMIT])
    with pytest.raises(ProviderRateLimitError):
        await provider.complete(_REQUEST)


async def test_server_error_behavior(provider) -> None:
    provider.script([ScriptedBehavior.SERVER_ERROR])
    with pytest.raises(ProviderUnavailableError):
        await provider.complete(_REQUEST)


async def test_transient_behavior(provider) -> None:
    provider.script([ScriptedBehavior.TRANSIENT])
    with pytest.raises(TransientProviderError):
        await provider.complete(_REQUEST)


async def test_cancelled_behavior(provider) -> None:
    provider.script([ScriptedBehavior.CANCELLED])
    with pytest.raises(ProviderCancelledError):
        await provider.complete(_REQUEST)


async def test_invalid_behavior_returns_empty_content(provider) -> None:
    provider.script([ScriptedBehavior.INVALID])
    response = await provider.complete(_REQUEST)
    assert response.content == ""


async def test_script_exhausts_to_default_behavior(provider) -> None:
    provider.script([ScriptedBehavior.SERVER_ERROR])
    with pytest.raises(ProviderUnavailableError):
        await provider.complete(_REQUEST)
    # Script exhausted -> default success
    response = await provider.complete(_REQUEST)
    assert response.content.startswith("[mock:")


async def test_pre_cancelled_token_aborts_immediately(provider) -> None:
    token = CancelToken()
    token.cancel()
    provider.script([ScriptedBehavior.SUCCESS])
    with pytest.raises(ProviderCancelledError):
        await provider.complete(_REQUEST, cancel_token=token)
