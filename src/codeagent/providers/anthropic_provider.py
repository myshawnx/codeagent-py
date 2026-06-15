"""Anthropic concrete provider.

Wraps the official ``AsyncAnthropic`` client and normalizes its response
objects into our provider-agnostic types. This is where all knowledge of the
Anthropic SDK's object shapes is confined.
"""

from __future__ import annotations

import asyncio

from .base import ProviderError, ProviderTimeoutError
from .types import (
    ModelRequest,
    ModelResponse,
    StopReason,
    TextBlock,
    TokenCount,
    ToolUseBlock,
    Usage,
)

# Anthropic stop_reason -> normalized StopReason
_STOP_REASON_MAP: dict[str, StopReason] = {
    "end_turn": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "stop_sequence": "stop_sequence",
}


class AnthropicProvider:
    """Provider backed by Anthropic's async Messages API."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        timeout_sec: float = 120.0,
        client: object | None = None,
    ):
        # Lazy import keeps the SDK out of the import path for offline tests.
        if client is not None:
            self._client = client
        else:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=api_key)
        self._timeout_sec = timeout_sec

    async def generate(self, request: ModelRequest) -> ModelResponse:
        kwargs = self._message_kwargs(request)
        kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        try:
            response = await asyncio.wait_for(
                self._client.messages.create(**kwargs),
                timeout=self._timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTimeoutError(
                f"Anthropic call exceeded {self._timeout_sec}s"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - normalize any SDK error
            raise ProviderError(f"Anthropic call failed: {exc}") from exc

        return self._normalize(response)

    async def count_tokens(self, request: ModelRequest) -> TokenCount:
        """Count request tokens using Anthropic's official Messages API."""
        kwargs = self._message_kwargs(request)

        try:
            response = await asyncio.wait_for(
                self._client.messages.count_tokens(**kwargs),
                timeout=self._timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTimeoutError(
                f"Anthropic token count exceeded {self._timeout_sec}s"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - normalize any SDK error
            raise ProviderError(f"Anthropic token count failed: {exc}") from exc

        return TokenCount(
            input_tokens=getattr(response, "input_tokens", 0),
            estimated=False,
            provider=self.name,
        )

    @staticmethod
    def _message_kwargs(request: ModelRequest) -> dict:
        kwargs: dict = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
        }
        if request.tools:
            kwargs["tools"] = [t.model_dump() for t in request.tools]
        if request.system:
            kwargs["system"] = request.system
        return kwargs

    @staticmethod
    def _normalize(response: object) -> ModelResponse:
        """Translate an Anthropic ``Message`` into a :class:`ModelResponse`."""
        content: list = []
        for block in getattr(response, "content", []):
            block_type = getattr(block, "type", None)
            if block_type == "text":
                content.append(TextBlock(text=getattr(block, "text", "")))
            elif block_type == "tool_use":
                content.append(
                    ToolUseBlock(
                        id=getattr(block, "id", ""),
                        name=getattr(block, "name", ""),
                        input=getattr(block, "input", {}) or {},
                    )
                )
            # Unknown block types are intentionally dropped.

        raw_stop = getattr(response, "stop_reason", None) or "end_turn"
        stop_reason = _STOP_REASON_MAP.get(raw_stop, "end_turn")

        usage_obj = getattr(response, "usage", None)
        usage = Usage(
            input_tokens=getattr(usage_obj, "input_tokens", 0) if usage_obj else 0,
            output_tokens=getattr(usage_obj, "output_tokens", 0) if usage_obj else 0,
        )

        return ModelResponse(
            content=content,
            stop_reason=stop_reason,
            usage=usage,
            model=getattr(response, "model", ""),
        )
