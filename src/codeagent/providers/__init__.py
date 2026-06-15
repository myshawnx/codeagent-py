"""Provider abstraction layer.

The runtime depends only on :class:`ModelProvider` and the normalized types in
``providers.types``. Concrete providers (Anthropic, Mock) live here.
"""

from .base import (
    ModelProvider,
    ProviderError,
    ProviderTimeoutError,
    TokenCountingNotSupported,
    count_tokens_with_fallback,
    estimate_model_request_tokens,
)
from .mock_provider import MockProvider, text_response, tool_use_response
from .types import (
    ContentBlock,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    StopReason,
    TextBlock,
    ToolResultBlock,
    ToolSchema,
    ToolUseBlock,
    TokenCount,
    Usage,
)

__all__ = [
    "ModelProvider",
    "ProviderError",
    "ProviderTimeoutError",
    "TokenCountingNotSupported",
    "count_tokens_with_fallback",
    "estimate_model_request_tokens",
    "MockProvider",
    "text_response",
    "tool_use_response",
    "ContentBlock",
    "ModelMessage",
    "ModelRequest",
    "ModelResponse",
    "StopReason",
    "TextBlock",
    "ToolResultBlock",
    "ToolSchema",
    "ToolUseBlock",
    "TokenCount",
    "Usage",
]


def create_anthropic_provider(
    api_key: str | None = None, timeout_sec: float = 120.0
) -> ModelProvider:
    """Factory that lazily imports the Anthropic SDK."""
    from .anthropic_provider import AnthropicProvider

    return AnthropicProvider(api_key=api_key, timeout_sec=timeout_sec)
