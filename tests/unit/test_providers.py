"""Tests for the provider abstraction layer."""

import asyncio

import pytest

from oricode.providers import (
    MockProvider,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ProviderError,
    TextBlock,
    TokenCount,
    TokenCountingNotSupported,
    ToolSchema,
    ToolUseBlock,
    Usage,
    count_tokens_with_fallback,
    text_response,
    tool_use_response,
)
from oricode.providers.anthropic_provider import AnthropicProvider


class _FakeUsage:
    def __init__(self, i, o):
        self.input_tokens = i
        self.output_tokens = o


class _FakeTokenCount:
    def __init__(self, input_tokens):
        self.input_tokens = input_tokens


class _FakeBlock:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeMessage:
    """Mimics the shape of an Anthropic Message object."""

    def __init__(self, content, stop_reason, usage, model="claude-x"):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage
        self.model = model


class _FakeStream:
    def __init__(self, chunks, final_message):
        self._chunks = chunks
        self._final_message = final_message
        self.text_stream = self._iter_text()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def _iter_text(self):
        for chunk in self._chunks:
            await asyncio.sleep(0)
            yield chunk

    async def get_final_message(self):
        return self._final_message


class TestAnthropicNormalization:
    """The provider must turn SDK objects into normalized types."""

    def test_normalize_text_and_tool_use(self):
        raw = _FakeMessage(
            content=[
                _FakeBlock(type="text", text="hello"),
                _FakeBlock(type="tool_use", id="t1", name="read", input={"file_path": "a.py"}),
            ],
            stop_reason="tool_use",
            usage=_FakeUsage(100, 20),
        )
        resp = AnthropicProvider._normalize(raw)

        assert isinstance(resp, ModelResponse)
        assert resp.stop_reason == "tool_use"
        assert resp.text() == "hello"
        assert len(resp.tool_uses()) == 1
        tu = resp.tool_uses()[0]
        assert isinstance(tu, ToolUseBlock)
        assert tu.id == "t1"
        assert tu.name == "read"
        assert tu.input == {"file_path": "a.py"}
        assert resp.usage.input_tokens == 100
        assert resp.usage.total_tokens == 120

    def test_normalize_unknown_stop_reason_defaults(self):
        raw = _FakeMessage(content=[], stop_reason="something_new", usage=_FakeUsage(1, 1))
        resp = AnthropicProvider._normalize(raw)
        assert resp.stop_reason == "end_turn"

    def test_normalize_drops_unknown_block_types(self):
        raw = _FakeMessage(
            content=[_FakeBlock(type="thinking", text="..."), _FakeBlock(type="text", text="ok")],
            stop_reason="end_turn",
            usage=_FakeUsage(0, 0),
        )
        resp = AnthropicProvider._normalize(raw)
        assert resp.text() == "ok"
        assert len(resp.content) == 1

    def test_normalize_missing_usage(self):
        raw = _FakeMessage(content=[], stop_reason="end_turn", usage=None)
        resp = AnthropicProvider._normalize(raw)
        assert resp.usage.total_tokens == 0


class TestUsage:
    def test_usage_addition(self):
        total = Usage(input_tokens=10, output_tokens=5) + Usage(input_tokens=3, output_tokens=2)
        assert total.input_tokens == 13
        assert total.output_tokens == 7
        assert total.total_tokens == 20


class TestTokenCount:
    def test_token_count_marks_provider_and_estimate(self):
        count = TokenCount(input_tokens=42, estimated=True, provider="fallback")
        assert count.input_tokens == 42
        assert count.estimated is True
        assert count.provider == "fallback"


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_scripted_responses_in_order(self):
        provider = MockProvider(responses=[text_response("first"), text_response("second")])
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])

        r1 = await provider.generate(req)
        r2 = await provider.generate(req)
        assert r1.text() == "first"
        assert r2.text() == "second"
        assert len(provider.calls) == 2

    @pytest.mark.asyncio
    async def test_exhaustion_raises(self):
        provider = MockProvider(responses=[text_response("only")])
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])
        await provider.generate(req)
        with pytest.raises(ProviderError):
            await provider.generate(req)

    @pytest.mark.asyncio
    async def test_handler_mode(self):
        def handler(request, index):
            return text_response(f"call-{index}")

        provider = MockProvider(handler=handler)
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])
        assert (await provider.generate(req)).text() == "call-0"
        assert (await provider.generate(req)).text() == "call-1"

    def test_requires_responses_or_handler(self):
        with pytest.raises(ValueError):
            MockProvider()

    @pytest.mark.asyncio
    async def test_count_tokens_fixed_value(self):
        provider = MockProvider(responses=[text_response("ok")], token_count=123)
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])

        count = await provider.count_tokens(req)

        assert count.input_tokens == 123
        assert count.estimated is False
        assert count.provider == "mock"
        assert provider.token_count_calls == [req]

    @pytest.mark.asyncio
    async def test_count_tokens_handler(self):
        def token_handler(request, index):
            return TokenCount(
                input_tokens=len(request.messages) + index,
                estimated=False,
                provider="scripted",
            )

        provider = MockProvider(responses=[text_response("ok")], token_count=token_handler)
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])

        assert (await provider.count_tokens(req)).input_tokens == 1
        assert (await provider.count_tokens(req)).input_tokens == 2

    @pytest.mark.asyncio
    async def test_count_tokens_default_is_estimated(self):
        provider = MockProvider(responses=[text_response("ok")])
        req = ModelRequest(
            model="m",
            messages=[ModelMessage(role="user", content=[{"type": "text", "text": "hello"}])],
        )

        count = await provider.count_tokens(req)

        assert count.input_tokens > 0
        assert count.estimated is True
        assert count.provider == "mock"

    @pytest.mark.asyncio
    async def test_stream_events_scripted(self):
        scripted = [
            ModelStreamEvent(type="message_start", payload={"model": "mock"}),
            ModelStreamEvent(type="text_delta", payload={"text": "hello"}),
            ModelStreamEvent(
                type="message_stop",
                payload={"response": text_response("hello").model_dump(mode="json")},
            ),
        ]
        provider = MockProvider(
            responses=[text_response("unused")],
            stream_events=[scripted],
        )
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])

        events = [event async for event in provider.stream(req)]

        assert [event.type for event in events] == [
            "message_start",
            "text_delta",
            "message_stop",
        ]
        assert events[1].payload["text"] == "hello"
        assert len(provider.calls) == 1

    @pytest.mark.asyncio
    async def test_stream_falls_back_to_scripted_response(self):
        provider = MockProvider(responses=[text_response("hello")])
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])

        events = [event async for event in provider.stream(req)]

        assert [event.type for event in events] == [
            "message_start",
            "text_delta",
            "message_stop",
        ]
        assert events[1].payload["text"] == "hello"


class TestTokenCountingFallback:
    @pytest.mark.asyncio
    async def test_provider_without_count_tokens_falls_back(self):
        class _LegacyProvider:
            name = "legacy"

            async def generate(self, request):
                return text_response("ok")

        req = ModelRequest(
            model="m",
            messages=[ModelMessage(role="user", content=[{"type": "text", "text": "hello"}])],
        )

        count = await count_tokens_with_fallback(_LegacyProvider(), req)

        assert count.input_tokens > 0
        assert count.estimated is True
        assert count.provider == "legacy"

    @pytest.mark.asyncio
    async def test_provider_can_signal_unsupported(self):
        class _UnsupportedProvider:
            name = "unsupported"

            async def count_tokens(self, request):
                raise TokenCountingNotSupported("not available")

        req = ModelRequest(
            model="m",
            messages=[ModelMessage(role="user", content=[{"type": "text", "text": "hello"}])],
        )

        count = await count_tokens_with_fallback(_UnsupportedProvider(), req)

        assert count.estimated is True
        assert count.provider == "unsupported"


class TestAnthropicProviderAsync:
    @pytest.mark.asyncio
    async def test_timeout_is_normalized(self):
        from oricode.providers.base import ProviderTimeoutError

        class _SlowMessages:
            async def create(self, **kw):
                await asyncio.sleep(10)

        class _SlowClient:
            messages = _SlowMessages()

        provider = AnthropicProvider(client=_SlowClient(), timeout_sec=0.01)
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])
        with pytest.raises(ProviderTimeoutError):
            await provider.generate(req)

    @pytest.mark.asyncio
    async def test_sdk_error_is_normalized(self):
        class _BoomMessages:
            async def create(self, **kw):
                raise RuntimeError("boom")

        class _BoomClient:
            messages = _BoomMessages()

        provider = AnthropicProvider(client=_BoomClient())
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])
        with pytest.raises(ProviderError):
            await provider.generate(req)

    @pytest.mark.asyncio
    async def test_builds_request_kwargs(self):
        captured = {}

        class _CaptureMessages:
            async def create(self, **kw):
                captured.update(kw)
                return _FakeMessage(
                    content=[_FakeBlock(type="text", text="ok")],
                    stop_reason="end_turn",
                    usage=_FakeUsage(1, 1),
                )

        class _CaptureClient:
            messages = _CaptureMessages()

        provider = AnthropicProvider(client=_CaptureClient())
        req = ModelRequest(
            model="claude-x",
            messages=[ModelMessage(role="user", content=[{"type": "text", "text": "hi"}])],
            system="be helpful",
        )
        resp = await provider.generate(req)
        assert resp.text() == "ok"
        assert captured["model"] == "claude-x"
        assert captured["system"] == "be helpful"
        assert captured["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_count_tokens_uses_official_messages_api(self):
        captured = {}

        class _CaptureMessages:
            async def count_tokens(self, **kw):
                captured.update(kw)
                return _FakeTokenCount(321)

        class _CaptureClient:
            messages = _CaptureMessages()

        provider = AnthropicProvider(client=_CaptureClient())
        req = ModelRequest(
            model="claude-x",
            messages=[ModelMessage(role="user", content=[{"type": "text", "text": "hi"}])],
            tools=[
                ToolSchema(
                    name="read",
                    description="Read a file",
                    input_schema={"type": "object"},
                )
            ],
            system="be helpful",
            max_tokens=99,
            temperature=0.2,
        )

        count = await provider.count_tokens(req)

        assert count.input_tokens == 321
        assert count.estimated is False
        assert count.provider == "anthropic"
        assert captured["model"] == "claude-x"
        assert captured["system"] == "be helpful"
        assert captured["messages"][0]["role"] == "user"
        assert captured["tools"][0]["name"] == "read"
        assert "max_tokens" not in captured
        assert "temperature" not in captured

    @pytest.mark.asyncio
    async def test_count_tokens_sdk_error_is_normalized(self):
        class _BoomMessages:
            async def count_tokens(self, **kw):
                raise RuntimeError("boom")

        class _BoomClient:
            messages = _BoomMessages()

        provider = AnthropicProvider(client=_BoomClient())
        req = ModelRequest(model="m", messages=[ModelMessage(role="user", content=[])])
        with pytest.raises(ProviderError, match="token count failed"):
            await provider.count_tokens(req)

    @pytest.mark.asyncio
    async def test_stream_yields_text_deltas_and_final_response(self):
        captured = {}
        final = _FakeMessage(
            content=[_FakeBlock(type="text", text="hello world")],
            stop_reason="end_turn",
            usage=_FakeUsage(10, 2),
        )

        class _CaptureMessages:
            def stream(self, **kw):
                captured.update(kw)
                return _FakeStream(["hello ", "world"], final)

        class _CaptureClient:
            messages = _CaptureMessages()

        provider = AnthropicProvider(client=_CaptureClient())
        req = ModelRequest(
            model="claude-x",
            messages=[ModelMessage(role="user", content=[{"type": "text", "text": "hi"}])],
            system="be helpful",
            max_tokens=99,
            temperature=0.2,
        )

        events = [event async for event in provider.stream(req)]

        assert [event.type for event in events] == [
            "message_start",
            "text_delta",
            "text_delta",
            "message_stop",
        ]
        assert events[1].payload["text"] == "hello "
        assert events[2].payload["text"] == "world"
        assert events[-1].payload["response"]["usage"]["input_tokens"] == 10
        assert captured["model"] == "claude-x"
        assert captured["max_tokens"] == 99
        assert captured["temperature"] == 0.2
