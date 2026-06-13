"""Agent main loop - core execution engine.

The loop is provider-agnostic: it speaks only :class:`ModelProvider` and the
normalized types in ``providers.types``. Every meaningful step emits a
structured :class:`Event` so traces, evals, and debugging share one source of
truth.
"""

from __future__ import annotations

from typing import Any

from ..providers import (
    ModelMessage,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ProviderError,
    TextBlock,
    ToolSchema,
    ToolUseBlock,
    Usage,
)
from .events import EventBus, EventType
from .extensions import ExtensionManager


class AgentLoop:
    """Drives the model<->tool conversation until the model stops."""

    def __init__(
        self,
        provider: ModelProvider,
        model: str,
        tools: dict[str, Any],  # {name: Tool}
        extension_manager: ExtensionManager,
        event_bus: EventBus,
        system: str | None = None,
        max_turns: int = 50,
    ):
        self.provider = provider
        self.model = model
        self.tools = tools
        self.extension_manager = extension_manager
        self.events = event_bus
        self.system = system
        self.max_turns = max_turns
        self.messages: list[ModelMessage] = []
        self.total_usage = Usage()

    async def run(self, prompt: str) -> str:
        """Run the agent loop and return the final assistant text."""
        self.messages.append(
            ModelMessage(role="user", content=[{"type": "text", "text": prompt}])
        )

        for turn in range(self.max_turns):
            turn_event = self.events.emit(EventType.TURN_START, {"turn": turn})

            try:
                response = await self._call_provider(parent_id=turn_event.id)
            except ProviderError as exc:
                self.events.emit(
                    EventType.ERROR,
                    {"stage": "model_request", "error": str(exc)},
                    parent_id=turn_event.id,
                )
                raise

            self._record_usage(response, parent_id=turn_event.id)

            # Persist the assistant turn verbatim so tool_use ids round-trip.
            assistant_content = [b.model_dump() for b in response.content]
            self.messages.append(
                ModelMessage(role="assistant", content=assistant_content)
            )

            if response.stop_reason == "tool_use":
                tool_results = await self._execute_tools(
                    response, parent_id=turn_event.id
                )
                self.messages.append(
                    ModelMessage(role="user", content=tool_results)
                )
                self.events.emit(
                    EventType.TURN_END,
                    {"turn": turn, "stop_reason": response.stop_reason},
                    parent_id=turn_event.id,
                )
                continue

            # Any non-tool stop reason terminates the loop.
            self.events.emit(
                EventType.TURN_END,
                {"turn": turn, "stop_reason": response.stop_reason},
                parent_id=turn_event.id,
            )
            return response.text()

        return "Maximum turns reached"

    async def _call_provider(self, parent_id: str | None) -> ModelResponse:
        tools_schema = [
            ToolSchema(
                name=tool.name,
                description=tool.description,
                input_schema=tool.parameters,
            )
            for tool in self.tools.values()
        ]
        request = ModelRequest(
            model=self.model,
            messages=self.messages,
            tools=tools_schema,
            system=self.system,
        )
        self.events.emit(
            EventType.MODEL_REQUEST,
            {
                "model": self.model,
                "num_messages": len(self.messages),
                "num_tools": len(tools_schema),
            },
            parent_id=parent_id,
        )
        response = await self.provider.generate(request)
        self.events.emit(
            EventType.MODEL_RESPONSE,
            {
                "stop_reason": response.stop_reason,
                "text": response.text()[:500],
                "tool_uses": [t.name for t in response.tool_uses()],
                "usage": response.usage.model_dump(),
            },
            parent_id=parent_id,
        )
        return response

    def _record_usage(self, response: ModelResponse, parent_id: str | None) -> None:
        self.total_usage = self.total_usage + response.usage
        self.extension_manager.fire_message_end(
            {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": self.total_usage.total_tokens,
            }
        )

    async def _execute_tools(
        self, response: ModelResponse, parent_id: str | None
    ) -> list[dict]:
        """Execute every tool-use block, returning normalized tool_result dicts."""
        tool_results: list[dict] = []

        for block in response.tool_uses():
            tool_results.append(await self._execute_one(block, parent_id))

        return tool_results

    async def _execute_one(self, block: ToolUseBlock, parent_id: str | None) -> dict:
        tool_use_id = block.id
        tool_name = block.name
        tool_input = block.input

        call_event = self.events.emit(
            EventType.TOOL_CALL_REQUESTED,
            {"tool": tool_name, "input": tool_input, "tool_use_id": tool_use_id},
            parent_id=parent_id,
        )

        # Extension hooks (policy + loop guards) may veto the call.
        verdict = self.extension_manager.fire_tool_call(tool_name, tool_input)
        blocked = bool(verdict and verdict.get("block"))
        self.events.emit(
            EventType.POLICY_VERDICT,
            {
                "tool": tool_name,
                "verdict": "deny" if blocked else "allow",
                "reason": verdict.get("reason") if verdict else None,
            },
            parent_id=call_event.id,
        )

        if blocked:
            reason = verdict.get("reason", "No reason given")
            return self._error_result(tool_use_id, f"Tool blocked: {reason}")

        tool = self.tools.get(tool_name)
        if tool is None:
            return self._error_result(tool_use_id, f"Tool not found: {tool_name}")

        self.events.emit(
            EventType.TOOL_START,
            {"tool": tool_name, "tool_use_id": tool_use_id},
            parent_id=call_event.id,
        )

        try:
            result = await tool.execute(**tool_input)
            result_str = str(result)
            self.extension_manager.fire_tool_result(tool_name, result, False)
            self.events.emit(
                EventType.TOOL_END,
                {
                    "tool": tool_name,
                    "tool_use_id": tool_use_id,
                    "is_error": False,
                    "result": result_str[:500],
                },
                parent_id=call_event.id,
            )
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result_str,
                "is_error": False,
            }
        except Exception as exc:  # noqa: BLE001 - surface as tool error to model
            error_msg = f"Tool execution failed: {exc}"
            self.extension_manager.fire_tool_result(tool_name, error_msg, True)
            self.events.emit(
                EventType.TOOL_END,
                {
                    "tool": tool_name,
                    "tool_use_id": tool_use_id,
                    "is_error": True,
                    "result": error_msg,
                },
                parent_id=call_event.id,
            )
            return self._error_result(tool_use_id, error_msg)

    @staticmethod
    def _error_result(tool_use_id: str, message: str) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": message,
            "is_error": True,
        }
