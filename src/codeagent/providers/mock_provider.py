"""Offline providers for tests and deterministic evals.

``MockProvider`` replays a fixed script of :class:`ModelResponse` objects,
optionally driven by a callable for input-dependent behavior. This lets the
full agent loop — tool calling, policy checks, event emission — be exercised
without any network access or API key.
"""

from __future__ import annotations

from typing import Callable

from .base import ProviderError
from .types import ModelRequest, ModelResponse, TextBlock, ToolUseBlock, Usage


class MockProvider:
    """A scripted provider.

    Pass either:
      * ``responses``: a list of :class:`ModelResponse` returned in order, or
      * ``handler``: ``(request, call_index) -> ModelResponse`` for dynamic
        behavior (e.g. respond to tool results).
    """

    name = "mock"

    def __init__(
        self,
        responses: list[ModelResponse] | None = None,
        handler: Callable[[ModelRequest, int], ModelResponse] | None = None,
    ):
        if responses is None and handler is None:
            raise ValueError("MockProvider requires either responses or handler")
        self._responses = responses or []
        self._handler = handler
        self.calls: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        index = len(self.calls)
        self.calls.append(request)

        if self._handler is not None:
            return self._handler(request, index)

        if index >= len(self._responses):
            raise ProviderError(
                f"MockProvider exhausted: requested response #{index} "
                f"but only {len(self._responses)} were scripted"
            )
        return self._responses[index]


# ---------------------------------------------------------------------------
# Convenience builders for common scripted responses
# ---------------------------------------------------------------------------


def text_response(text: str, *, input_tokens: int = 10, output_tokens: int = 5) -> ModelResponse:
    """A terminal assistant turn that just returns text."""
    return ModelResponse(
        content=[TextBlock(text=text)],
        stop_reason="end_turn",
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        model="mock",
    )


def tool_use_response(
    tool_id: str,
    name: str,
    tool_input: dict,
    *,
    text: str | None = None,
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> ModelResponse:
    """An assistant turn requesting a single tool call."""
    content: list = []
    if text:
        content.append(TextBlock(text=text))
    content.append(ToolUseBlock(id=tool_id, name=name, input=tool_input))
    return ModelResponse(
        content=content,
        stop_reason="tool_use",
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        model="mock",
    )
