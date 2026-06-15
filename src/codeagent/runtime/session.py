"""Agent Session - session management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..context import build_system_prompt, load_project_instructions
from ..context.profile import detect_profile
from ..providers import ModelProvider, create_anthropic_provider
from .events import Event, EventBus, EventType
from .extensions import Extension, ExtensionAPI, ExtensionManager
from .loop import AgentLoop
from .tools import create_builtin_tools
from .types import Tool

DEFAULT_SYSTEM_PROMPT = """You are CodeAgent, a careful local coding assistant.

You operate inside a user's workspace with policy-enforced tools. Guidelines:
- Prefer reading and understanding code before editing it.
- Make minimal, targeted changes that satisfy the request.
- Use the `edit` or `apply_patch` tools for changes rather than rewriting whole files.
- When a tool is blocked by policy, explain the situation instead of retrying blindly.
- Stop when the task is complete; do not perform unrelated work.
"""


class SessionAPI(ExtensionAPI):
    """ExtensionAPI implemented against an :class:`AgentSession`."""

    def __init__(self, session: "AgentSession"):
        self.session = session

    def register_tool(self, tool: Tool) -> None:
        self.session.register_tool(tool)

    def set_active_tools(self, names: list[str]) -> None:
        self.session.set_active_tools(names)

    def append_entry(self, entry_type: str, data: dict) -> None:
        self.session.append_entry(entry_type, data)

    def send_message(self, content: str) -> None:
        # Reserved for future bidirectional extension messaging.
        pass


class AgentSession:
    """A single agent session: owns tools, extensions, and the event bus."""

    def __init__(
        self,
        cwd: str,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        extensions: list[Extension] | None = None,
        provider: ModelProvider | None = None,
        event_bus: EventBus | None = None,
        system: str | None = None,
        timeout_sec: float = 120.0,
        load_context: bool = True,
    ):
        self.cwd = cwd
        self.model = model
        # Provider injection keeps the session testable offline.
        self.provider = provider or create_anthropic_provider(
            api_key=api_key, timeout_sec=timeout_sec
        )
        self.events = event_bus or EventBus()

        # Build system prompt from project context if requested.
        if load_context and system is None:
            profile = detect_profile(cwd)
            instructions = load_project_instructions(cwd)
            self.system = build_system_prompt(
                DEFAULT_SYSTEM_PROMPT,
                profile=profile,
                project_instructions=instructions,
            )
        else:
            self.system = system or DEFAULT_SYSTEM_PROMPT

        # Tools
        self.tools: dict[str, Tool] = {}
        self.active_tool_names: list[str] = []

        # Custom entries (legacy trajectory log; events are the modern path)
        self.custom_entries: list[dict] = []

        # Extensions
        self.extensions = extensions or []
        self.extension_api = SessionAPI(self)
        self.extension_manager = ExtensionManager(self.extensions, self.extension_api)

        # Register builtin tools
        builtin_tools = create_builtin_tools(cwd)
        for tool in builtin_tools:
            self.register_tool(tool)
        self.set_active_tools([t.name for t in builtin_tools])

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def set_active_tools(self, names: list[str]) -> None:
        self.active_tool_names = names

    def append_entry(self, entry_type: str, data: dict) -> None:
        self.custom_entries.append({"type": entry_type, "data": data})

    async def run(self, prompt: str) -> str:
        """Run the agent against ``prompt`` and return the final text."""
        self.events.emit(
            EventType.SESSION_START,
            {"cwd": self.cwd, "model": self.model, "prompt": prompt},
        )
        self.extension_manager.fire_session_start()

        active_tools = {
            name: self.tools[name]
            for name in self.active_tool_names
            if name in self.tools
        }

        loop = AgentLoop(
            provider=self.provider,
            model=self.model,
            tools=active_tools,
            extension_manager=self.extension_manager,
            event_bus=self.events,
            system=self.system,
        )

        try:
            result = await loop.run(prompt)
            self.events.emit(
                EventType.SESSION_END,
                {
                    "result": result[:500],
                    "total_tokens": loop.total_usage.total_tokens,
                },
            )
            return result
        except Exception as exc:  # noqa: BLE001
            self.events.emit(EventType.ERROR, {"stage": "session", "error": str(exc)})
            self.events.emit(EventType.SESSION_END, {"error": str(exc)})
            raise
        finally:
            self.extension_manager.fire_session_end()

    async def run_stream(self, prompt: str) -> AsyncIterator[Event]:
        """Run the agent and yield runtime events as they occur."""
        event = self.events.emit(
            EventType.SESSION_START,
            {"cwd": self.cwd, "model": self.model, "prompt": prompt},
        )
        yield event
        self.extension_manager.fire_session_start()

        active_tools = {
            name: self.tools[name]
            for name in self.active_tool_names
            if name in self.tools
        }

        loop = AgentLoop(
            provider=self.provider,
            model=self.model,
            tools=active_tools,
            extension_manager=self.extension_manager,
            event_bus=self.events,
            system=self.system,
        )

        try:
            async for event in loop.run_stream(prompt):
                yield event
            result = loop.last_result or ""
            event = self.events.emit(
                EventType.SESSION_END,
                {
                    "result": result[:500],
                    "total_tokens": loop.total_usage.total_tokens,
                },
            )
            yield event
        except Exception as exc:  # noqa: BLE001
            event = self.events.emit(
                EventType.ERROR,
                {"stage": "session", "error": str(exc)},
            )
            yield event
            event = self.events.emit(EventType.SESSION_END, {"error": str(exc)})
            yield event
            raise
        finally:
            self.extension_manager.fire_session_end()
