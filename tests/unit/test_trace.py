"""Tests for P2 JSONL session tracing."""

import json
from pathlib import Path

import pytest

from codeagent.providers import MockProvider, text_response, tool_use_response
from codeagent.runtime.events import Event, EventBus, EventType
from codeagent.runtime.session import AgentSession
from codeagent.trace import (
    TraceReconstructionError,
    TraceWriter,
    attach_trace_writer,
    find_session_trace,
    get_trace_dir,
    list_sessions,
    read_trace,
    reconstruct_messages,
    save_session_trace,
)


class TestTraceWriterRoundTrip:
    """JSONL write/read round-trip tests."""

    def test_write_and_read_events(self, temp_repo):
        trace_path = Path(temp_repo) / "test.jsonl"
        bus = EventBus(session_id="test-session")

        # Attach writer.
        writer = attach_trace_writer(bus, trace_path)

        # Emit events.
        bus.emit(EventType.SESSION_START, {"foo": "bar"})
        bus.emit(EventType.TURN_START, {"turn": 0})
        bus.emit(EventType.SESSION_END, {})

        writer.close()

        # Read back.
        events = read_trace(trace_path)
        assert len(events) == 3
        assert events[0].type == EventType.SESSION_START
        assert events[0].payload == {"foo": "bar"}
        assert events[1].type == EventType.TURN_START
        assert events[2].type == EventType.SESSION_END

    def test_malformed_lines_are_skipped(self, temp_repo):
        trace_path = Path(temp_repo) / "bad.jsonl"
        trace_path.write_text('{"type": "session_start", "session_id": "s1", "payload": {}}\n'
                               'not json\n'
                               '{"type": "session_end", "session_id": "s1", "payload": {}}\n')

        events = read_trace(trace_path)
        assert len(events) == 2  # malformed line skipped
        assert events[0].type == EventType.SESSION_START
        assert events[1].type == EventType.SESSION_END

    def test_read_nonexistent_trace(self, temp_repo):
        events = read_trace(Path(temp_repo) / "nonexistent.jsonl")
        assert events == []

    def test_trace_writer_implements_sink_write(self, temp_repo):
        trace_path = Path(temp_repo) / "sink.jsonl"
        writer = TraceWriter(trace_path)
        writer.write(Event(EventType.SESSION_START, session_id="sink", payload={}))
        writer.close()

        events = read_trace(trace_path)
        assert len(events) == 1
        assert events[0].session_id == "sink"


class TestSessionTracePersistence:
    """save_session_trace and list_sessions."""

    def test_save_and_list_sessions(self, temp_repo):
        bus1 = EventBus(session_id="session-1")
        bus1.emit(EventType.SESSION_START, {})
        bus1.emit(EventType.SESSION_END, {})

        bus2 = EventBus(session_id="session-2")
        bus2.emit(EventType.SESSION_START, {})

        # Save both.
        save_session_trace(temp_repo, "session-1", bus1.events)
        save_session_trace(temp_repo, "session-2", bus2.events)

        # List.
        sessions = list_sessions(temp_repo)
        assert len(sessions) == 2
        assert sessions[0]["session_id"] in ["session-1", "session-2"]
        assert sessions[0]["event_count"] in [1, 2]

    def test_list_sessions_empty(self, temp_repo):
        sessions = list_sessions(temp_repo)
        assert sessions == []

    def test_find_session_trace_by_prefix(self, temp_repo):
        bus = EventBus(session_id="abcdef123456")
        bus.emit(EventType.SESSION_START, {})
        save_session_trace(temp_repo, bus.session_id, bus.events)

        trace_path = find_session_trace(temp_repo, "abcdef")

        assert trace_path is not None
        assert trace_path.name == "abcdef123456.jsonl"


class TestTraceReconstruction:
    """Reconstruct normalized messages for linear resume."""

    def test_reconstruct_simple_text_turn(self):
        bus = EventBus(session_id="resume-simple")
        bus.emit(
            EventType.MODEL_REQUEST,
            {
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": "hello"}]}
                ]
            },
        )
        bus.emit(
            EventType.MODEL_RESPONSE,
            {
                "content": [{"type": "text", "text": "hi"}],
            },
        )

        messages = reconstruct_messages(bus.events)

        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[0].content[0]["text"] == "hello"
        assert messages[1].content[0]["text"] == "hi"

    def test_reconstruct_tool_use_and_tool_result(self):
        tool_turn = tool_use_response("t1", "read", {"file_path": "a.py"})
        bus = EventBus(session_id="resume-tools")
        bus.emit(
            EventType.MODEL_REQUEST,
            {
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": "read a.py"}]}
                ]
            },
        )
        bus.emit(
            EventType.MODEL_RESPONSE,
            {
                "content": [b.model_dump(mode="json") for b in tool_turn.content],
            },
        )
        bus.emit(
            EventType.MODEL_REQUEST,
            {
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": "read a.py"}]},
                    {
                        "role": "assistant",
                        "content": [b.model_dump(mode="json") for b in tool_turn.content],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "t1",
                                "content": "print('ok')",
                                "is_error": False,
                            }
                        ],
                    },
                ]
            },
        )
        bus.emit(
            EventType.MODEL_RESPONSE,
            {
                "content": [{"type": "text", "text": "done"}],
            },
        )

        messages = reconstruct_messages(bus.events)

        assert [m.role for m in messages] == ["user", "assistant", "user", "assistant"]
        assert messages[1].content[0]["type"] == "tool_use"
        assert messages[2].content[0]["type"] == "tool_result"
        assert messages[3].content[0]["text"] == "done"

    def test_reconstruct_corrupted_trace_fails_safely(self):
        bus = EventBus(session_id="bad-resume")
        bus.emit(EventType.MODEL_REQUEST, {"num_messages": 1})

        with pytest.raises(TraceReconstructionError):
            reconstruct_messages(bus.events)

    @pytest.mark.asyncio
    async def test_resume_session_sends_history_to_provider(self, temp_repo):
        initial_messages = reconstruct_messages(
            [
                Event(
                    type=EventType.MODEL_REQUEST,
                    session_id="s1",
                    payload={
                        "messages": [
                            {
                                "role": "user",
                                "content": [{"type": "text", "text": "original prompt"}],
                            }
                        ]
                    },
                ),
                Event(
                    type=EventType.MODEL_RESPONSE,
                    session_id="s1",
                    payload={"content": [{"type": "text", "text": "original answer"}]},
                ),
            ]
        )
        provider = MockProvider(responses=[text_response("continued")])
        session = AgentSession(
            cwd=temp_repo,
            provider=provider,
            initial_messages=initial_messages,
        )

        await session.run("continue")

        sent = provider.calls[0].messages
        assert [m.role for m in sent] == ["user", "assistant", "user"]
        assert sent[0].content[0]["text"] == "original prompt"
        assert sent[1].content[0]["text"] == "original answer"
        assert sent[2].content[0]["text"] == "continue"


class TestTraceIntegrationWithSession:
    """Full agent session with trace capture."""

    @pytest.mark.asyncio
    async def test_session_events_captured_in_trace(self, temp_repo):
        provider = MockProvider(responses=[text_response("done")])
        bus = EventBus()
        trace_dir = get_trace_dir(temp_repo)
        trace_path = trace_dir / f"{bus.session_id}.jsonl"
        writer = attach_trace_writer(bus, trace_path)

        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=bus)
        await session.run("test")

        writer.close()

        # Read trace back.
        events = read_trace(trace_path)
        assert len(events) > 0

        # Should have session lifecycle events.
        types = [e.type for e in events]
        assert EventType.SESSION_START in types
        assert EventType.TURN_START in types
        assert EventType.MODEL_REQUEST in types
        assert EventType.MODEL_RESPONSE in types
        assert EventType.SESSION_END in types
