"""Tests for the runtime event model and offline agent loop."""

import asyncio

import pytest

from codeagent.providers import (
    MockProvider,
    ModelResponse,
    ModelStreamEvent,
    ProviderError,
    ToolUseBlock,
    text_response,
    tool_use_response,
)
from codeagent.runtime.events import Event, EventBus, EventType
from codeagent.runtime.session import AgentSession
from codeagent.runtime.tools import create_builtin_tools
from codeagent.runtime.types import Tool


class TestEventBus:
    def test_emit_and_collect(self):
        bus = EventBus(session_id="test-session")
        bus.emit(EventType.SESSION_START, {"foo": "bar"})
        bus.emit(EventType.TURN_START, {"turn": 0})

        assert len(bus.events) == 2
        assert bus.events[0].type == EventType.SESSION_START
        assert bus.events[0].session_id == "test-session"
        assert bus.events[0].payload == {"foo": "bar"}
        assert bus.events[1].type == EventType.TURN_START

    def test_by_type_filter(self):
        bus = EventBus()
        bus.emit(EventType.SESSION_START, {})
        bus.emit(EventType.TURN_START, {})
        bus.emit(EventType.TURN_START, {})

        starts = bus.by_type(EventType.TURN_START)
        assert len(starts) == 2

    def test_subscriber_receives_events(self):
        bus = EventBus()
        collected = []

        def listener(evt):
            collected.append(evt.type)

        bus.subscribe(listener)
        bus.emit(EventType.SESSION_START, {})
        bus.emit(EventType.SESSION_END, {})

        assert collected == [EventType.SESSION_START, EventType.SESSION_END]

    def test_failing_subscriber_does_not_crash(self):
        bus = EventBus()

        def bad_listener(evt):
            raise RuntimeError("boom")

        bus.subscribe(bad_listener)
        # Should not raise
        bus.emit(EventType.SESSION_START, {})
        assert len(bus.events) == 1


class TestEventSerialization:
    def test_to_dict_and_from_dict(self):
        original = Event(
            type=EventType.TOOL_START,
            session_id="s1",
            payload={"tool": "read", "file": "a.py"},
            parent_id="p1",
        )
        data = original.to_dict()

        assert data["type"] == "tool_start"
        assert data["session_id"] == "s1"
        assert data["payload"]["tool"] == "read"

        restored = Event.from_dict(data)
        assert restored.type == EventType.TOOL_START
        assert restored.session_id == "s1"
        assert restored.payload == {"tool": "read", "file": "a.py"}
        assert restored.parent_id == "p1"


class TestOfflineAgentLoop:
    """Full agent loop run with MockProvider — no network, no API key."""

    @pytest.mark.asyncio
    async def test_single_turn_text_response(self, temp_repo):
        provider = MockProvider(responses=[text_response("All done!")])
        bus = EventBus()

        session = AgentSession(
            cwd=temp_repo,
            provider=provider,
            event_bus=bus,
        )

        result = await session.run("Do something")

        assert result == "All done!"
        assert len(provider.calls) == 1
        assert provider.calls[0].messages[0].content[0]["text"] == "Do something"

        # Verify events were emitted.
        assert len(bus.by_type(EventType.SESSION_START)) == 1
        assert len(bus.by_type(EventType.TURN_START)) == 1
        assert len(bus.by_type(EventType.MODEL_REQUEST)) == 1
        assert len(bus.by_type(EventType.MODEL_RESPONSE)) == 1
        assert len(bus.by_type(EventType.SESSION_END)) == 1

    @pytest.mark.asyncio
    async def test_tool_call_flow(self, temp_repo):
        # The mock will request a tool, we'll execute it, then end.
        provider = MockProvider(
            responses=[
                tool_use_response("t1", "read", {"file_path": "test.txt"}),
                text_response("File read successfully"),
            ]
        )
        bus = EventBus()

        # Write a file so the read tool succeeds.
        from pathlib import Path

        test_file = Path(temp_repo) / "test.txt"
        test_file.write_text("hello world")

        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=bus)
        result = await session.run("Read test.txt")

        assert result == "File read successfully"
        assert len(provider.calls) == 2

        # Second call should have tool_result in messages.
        second_call = provider.calls[1]
        last_msg = second_call.messages[-1]
        assert last_msg.role == "user"
        # Should have a tool_result block.
        assert len(last_msg.content) == 1
        assert last_msg.content[0]["type"] == "tool_result"
        assert last_msg.content[0]["tool_use_id"] == "t1"
        assert "hello world" in last_msg.content[0]["content"]

        # Events.
        assert len(bus.by_type(EventType.TOOL_CALL_REQUESTED)) == 1
        assert len(bus.by_type(EventType.TOOL_START)) == 1
        assert len(bus.by_type(EventType.TOOL_END)) == 1
        tool_end = bus.by_type(EventType.TOOL_END)[0]
        assert not tool_end.payload["is_error"]

    @pytest.mark.asyncio
    async def test_parallel_safe_tools_execute_concurrently_in_order(self, temp_repo):
        running = 0
        max_running = 0

        async def slow_read(value: str) -> str:
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.01)
            running -= 1
            return value

        provider = MockProvider(
            responses=[
                ModelResponse(
                    content=[
                        ToolUseBlock(id="t1", name="slow_read", input={"value": "first"}),
                        ToolUseBlock(id="t2", name="slow_read", input={"value": "second"}),
                    ],
                    stop_reason="tool_use",
                    model="mock",
                ),
                text_response("done"),
            ]
        )
        bus = EventBus()
        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=bus)
        session.register_tool(
            Tool(
                name="slow_read",
                description="Slow read-only tool",
                parameters={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
                execute=slow_read,
                parallel_safe=True,
            )
        )
        session.set_active_tools(["slow_read"])

        result = await session.run("Run both reads")

        assert result == "done"
        assert max_running == 2
        tool_results = provider.calls[1].messages[-1].content
        assert [item["tool_use_id"] for item in tool_results] == ["t1", "t2"]
        assert [item["content"] for item in tool_results] == ["first", "second"]
        assert [event.payload["tool_use_id"] for event in bus.by_type(EventType.TOOL_END)] == [
            "t1",
            "t2",
        ]

    @pytest.mark.asyncio
    async def test_mutating_tools_remain_serial(self, temp_repo):
        running = 0
        max_running = 0

        async def mutate(value: str) -> str:
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.01)
            running -= 1
            return value

        provider = MockProvider(
            responses=[
                ModelResponse(
                    content=[
                        ToolUseBlock(id="t1", name="mutate", input={"value": "first"}),
                        ToolUseBlock(id="t2", name="mutate", input={"value": "second"}),
                    ],
                    stop_reason="tool_use",
                    model="mock",
                ),
                text_response("done"),
            ]
        )
        session = AgentSession(cwd=temp_repo, provider=provider)
        session.register_tool(
            Tool(
                name="mutate",
                description="Mutating tool",
                parameters={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
                execute=mutate,
                mutates_workspace=True,
            )
        )
        session.set_active_tools(["mutate"])

        await session.run("Run both mutations")

        assert max_running == 1

    @pytest.mark.asyncio
    async def test_tool_not_found_error(self, temp_repo):
        provider = MockProvider(
            responses=[
                tool_use_response("t2", "unknown_tool", {}),
                text_response("Handled error"),
            ]
        )
        bus = EventBus()

        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=bus)
        result = await session.run("Do unknown")

        assert result == "Handled error"

        # The tool_result should be an error.
        second_call = provider.calls[1]
        tool_result = second_call.messages[-1].content[0]
        assert tool_result["is_error"] is True
        assert "Tool not found" in tool_result["content"]

    @pytest.mark.asyncio
    async def test_tool_execution_failure(self, temp_repo):
        provider = MockProvider(
            responses=[
                tool_use_response("t3", "read", {"file_path": "missing.txt"}),
                text_response("Handled missing file"),
            ]
        )
        bus = EventBus()

        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=bus)
        result = await session.run("Read missing file")

        assert result == "Handled missing file"

        # Tool result should show the error.
        tool_result = provider.calls[1].messages[-1].content[0]
        assert tool_result["is_error"] is True
        assert "File not found" in tool_result["content"]

        # TOOL_END event should mark it as error.
        tool_end = bus.by_type(EventType.TOOL_END)[0]
        assert tool_end.payload["is_error"] is True

    @pytest.mark.asyncio
    async def test_policy_blocks_tool(self, temp_repo):
        from codeagent.config.schema import ApprovalMode, PathPolicy, PolicyConfig
        from codeagent.policy.gateway import PolicyGateway

        provider = MockProvider(
            responses=[
                tool_use_response("t4", "write", {"file_path": ".env", "content": "SECRET=1"}),
                text_response("Understood restriction"),
            ]
        )
        bus = EventBus()
        policy = PolicyConfig(path=PathPolicy(deny=[".env", ".ssh/*", "**/*.key"]))
        policy_ext = PolicyGateway(
            policy=policy, mode=ApprovalMode.WORKSPACE_WRITE, repo_root=temp_repo
        )

        session = AgentSession(
            cwd=temp_repo,
            provider=provider,
            event_bus=bus,
            extensions=[policy_ext],
        )
        result = await session.run("Write to .env")

        assert result == "Understood restriction"

        # The tool should have been blocked.
        tool_result = provider.calls[1].messages[-1].content[0]
        assert tool_result["is_error"] is True
        assert "Tool blocked" in tool_result["content"]

        # Events should show policy verdict = deny.
        verdicts = bus.by_type(EventType.POLICY_VERDICT)
        assert len(verdicts) == 1
        assert verdicts[0].payload["verdict"] == "deny"

        # TOOL_START/TOOL_END should NOT be emitted if policy blocked.
        assert len(bus.by_type(EventType.TOOL_START)) == 0
        assert len(bus.by_type(EventType.TOOL_END)) == 0

    @pytest.mark.asyncio
    async def test_system_prompt_passed_to_provider(self, temp_repo):
        provider = MockProvider(responses=[text_response("ok")])

        session = AgentSession(
            cwd=temp_repo,
            provider=provider,
            system="Custom system prompt",
        )
        await session.run("Test")

        # Check the request had the system prompt.
        assert provider.calls[0].system == "Custom system prompt"

    def test_builtin_tool_parallel_metadata(self, temp_repo):
        tools = {tool.name: tool for tool in create_builtin_tools(temp_repo)}

        assert tools["read"].parallel_safe is True
        assert tools["git_diff"].parallel_safe is True
        assert tools["write"].mutates_workspace is True
        assert tools["edit"].mutates_workspace is True
        assert tools["apply_patch"].mutates_workspace is True
        assert tools["bash"].mutates_workspace is True

    @pytest.mark.asyncio
    async def test_streaming_text_response(self, temp_repo):
        response = text_response("All done!", input_tokens=7, output_tokens=3)
        provider = MockProvider(
            responses=[text_response("unused")],
            stream_events=[
                [
                    ModelStreamEvent(type="message_start", payload={"model": "mock"}),
                    ModelStreamEvent(type="text_delta", payload={"text": "All "}),
                    ModelStreamEvent(type="text_delta", payload={"text": "done!"}),
                    ModelStreamEvent(
                        type="message_stop",
                        payload={"response": response.model_dump(mode="json")},
                    ),
                ]
            ],
        )
        bus = EventBus()
        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=bus)

        events = [event async for event in session.run_stream("Do something")]

        deltas = [e.payload["text"] for e in events if e.type == EventType.MODEL_TEXT_DELTA]
        assert deltas == ["All ", "done!"]
        assert len(bus.by_type(EventType.MODEL_STREAM_START)) == 1
        assert len(bus.by_type(EventType.MODEL_STREAM_END)) == 1
        assert bus.by_type(EventType.MODEL_RESPONSE)[0].payload["text"] == "All done!"
        assert bus.by_type(EventType.SESSION_END)[0].payload["result"] == "All done!"
        assert bus.by_type(EventType.SESSION_END)[0].payload["total_tokens"] == 10

    @pytest.mark.asyncio
    async def test_streaming_tool_call_continues_loop(self, temp_repo):
        from pathlib import Path

        test_file = Path(temp_repo) / "test.txt"
        test_file.write_text("hello world")
        tool_response = tool_use_response("t1", "read", {"file_path": "test.txt"})
        final_response = text_response("File read successfully")
        provider = MockProvider(
            responses=[text_response("unused")],
            stream_events=[
                [
                    ModelStreamEvent(type="message_start", payload={"model": "mock"}),
                    ModelStreamEvent(
                        type="message_stop",
                        payload={"response": tool_response.model_dump(mode="json")},
                    ),
                ],
                [
                    ModelStreamEvent(type="message_start", payload={"model": "mock"}),
                    ModelStreamEvent(
                        type="text_delta",
                        payload={"text": "File read successfully"},
                    ),
                    ModelStreamEvent(
                        type="message_stop",
                        payload={"response": final_response.model_dump(mode="json")},
                    ),
                ],
            ],
        )
        bus = EventBus()
        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=bus)

        events = [event async for event in session.run_stream("Read test.txt")]

        assert len(provider.calls) == 2
        second_call = provider.calls[1]
        assert second_call.messages[-1].content[0]["type"] == "tool_result"
        assert "hello world" in second_call.messages[-1].content[0]["content"]
        assert len([e for e in events if e.type == EventType.TOOL_CALL_REQUESTED]) == 1
        assert bus.by_type(EventType.SESSION_END)[0].payload["result"] == (
            "File read successfully"
        )

    @pytest.mark.asyncio
    async def test_stream_error_becomes_runtime_event(self, temp_repo):
        provider = MockProvider(
            responses=[text_response("unused")],
            stream_events=[
                [
                    ModelStreamEvent(type="message_start", payload={"model": "mock"}),
                    ModelStreamEvent(type="error", payload={"error": "stream exploded"}),
                ]
            ],
        )
        bus = EventBus()
        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=bus)

        with pytest.raises(ProviderError):
            async for _event in session.run_stream("Do something"):
                pass

        errors = bus.by_type(EventType.ERROR)
        assert any("stream exploded" in event.payload.get("error", "") for event in errors)
