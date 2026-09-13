"""Runtime + model-abstraction errors (STEP 5).

Every error derives from :class:`aiagent.core.errors.AiAgentError` so the API
envelope handler maps it uniformly.  ``is_retryable`` is the single source of
truth for the retry classifier used by :class:`aiagent.runtime.service.
AgentRuntimeService`.

Never embed raw provider payloads or credentials in these messages - handlers
may surface ``message`` to users.
"""

from __future__ import annotations

from aiagent.core.errors import AiAgentError


class ModelError(AiAgentError):
    """Base class for model-call failures (provider-level)."""

    status_code = 502
    error_code = "model_error"


class ModelConfigurationError(AiAgentError):
    """The agent's model configuration is incomplete or invalid (non-retryable)."""

    status_code = 500
    error_code = "model_configuration_error"


class ProviderNotFoundError(ModelError):
    """No provider is registered under the requested name (non-retryable)."""

    error_code = "provider_not_found"


class ProviderUnavailableError(ModelError):
    """The provider is down / returned a 5xx (retryable)."""

    error_code = "provider_unavailable"


class ProviderTimeoutError(ModelError):
    """The provider did not answer within the timeout (retryable)."""

    status_code = 504
    error_code = "provider_timeout"


class ProviderRateLimitError(ModelError):
    """The provider rate-limited the request (retryable)."""

    status_code = 429
    error_code = "provider_rate_limit"


class TransientProviderError(ModelError):
    """Unexpected transient provider failure (retryable)."""

    error_code = "provider_transient_failure"


class InvalidModelResponseError(ModelError):
    """The provider returned structurally invalid output (non-retryable)."""

    error_code = "invalid_model_response"


class ProviderCancelledError(AiAgentError):
    """Execution was cancelled (via the caller's cancel token)."""

    status_code = 499
    error_code = "provider_cancelled"


_RETRYABLE: tuple[type[AiAgentError], ...] = (
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    TransientProviderError,
)


def is_retryable(exc: BaseException) -> bool:
    """Classify an error as transient/retryable (used by the runtime retry loop)."""
    return isinstance(exc, _RETRYABLE)
