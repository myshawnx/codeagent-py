"""Tests for the provider abstraction layer."""

import asyncio

import pytest

from codeagent.providers import (
    MockProvider,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ProviderError,
    TextBlock,
    ToolUseBlock,
    Usage,
    text_response,
    tool_use_response,
)
from codeagent.providers.anthropic_provider import AnthropicProvider


class _FakeUsage:
    def __init__(self, i, o):
        self.input_tokens = i
        self.output_tokens = o


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


class TestAnthropicProviderAsync:
    @pytest.mark.asyncio
    async def test_timeout_is_normalized(self):
        from codeagent.providers.base import ProviderTimeoutError

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
