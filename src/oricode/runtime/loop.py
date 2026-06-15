"""Agent main loop - core execution engine.

The loop is provider-agnostic: it speaks only :class:`ModelProvider` and the
normalized types in ``providers.types``. Every meaningful step emits a
structured :class:`Event` so traces, evals, and debugging share one source of
truth.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
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
    stream_with_fallback,
)
from .events import Event, EventBus, EventType
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
        self.last_result: str | None = None

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
            self.last_result = response.text()
            return self.last_result

        self.last_result = "Maximum turns reached"
        return self.last_result

    async def run_stream(self, prompt: str) -> AsyncIterator[Event]:
        """Run the agent loop and yield runtime events as they occur."""
        self.messages.append(
            ModelMessage(role="user", content=[{"type": "text", "text": prompt}])
        )

        for turn in range(self.max_turns):
            turn_event = self.events.emit(EventType.TURN_START, {"turn": turn})
            yield turn_event

            try:
                response: ModelResponse | None = None
                async for event, maybe_response in self._call_provider_stream(
                    parent_id=turn_event.id
                ):
                    yield event
                    if maybe_response is not None:
                        response = maybe_response
                if response is None:
                    raise ProviderError("Provider stream ended without final response")
            except ProviderError as exc:
                event = self.events.emit(
                    EventType.ERROR,
                    {"stage": "model_request", "error": str(exc)},
                    parent_id=turn_event.id,
                )
                yield event
                raise

            self._record_usage(response, parent_id=turn_event.id)

            assistant_content = [b.model_dump() for b in response.content]
            self.messages.append(
                ModelMessage(role="assistant", content=assistant_content)
            )

            if response.stop_reason == "tool_use":
                event_start = len(self.events.events)
                tool_results = await self._execute_tools(
                    response, parent_id=turn_event.id
                )
                for event in self.events.events[event_start:]:
                    yield event
                self.messages.append(ModelMessage(role="user", content=tool_results))
                event = self.events.emit(
                    EventType.TURN_END,
                    {"turn": turn, "stop_reason": response.stop_reason},
                    parent_id=turn_event.id,
                )
                yield event
                continue

            event = self.events.emit(
                EventType.TURN_END,
                {"turn": turn, "stop_reason": response.stop_reason},
                parent_id=turn_event.id,
            )
            yield event
            self.last_result = response.text()
            return

        self.last_result = "Maximum turns reached"

    async def _call_provider(self, parent_id: str | None) -> ModelResponse:
        request = self._build_model_request()
        self._emit_model_request(request, parent_id=parent_id)
        response = await self.provider.generate(request)
        self._emit_model_response(response, parent_id=parent_id)
        return response

    async def _call_provider_stream(
        self, parent_id: str | None
    ) -> AsyncIterator[tuple[Event, ModelResponse | None]]:
        request = self._build_model_request()
        yield self._emit_model_request(request, parent_id=parent_id), None

        text_parts: list[str] = []
        final_response: ModelResponse | None = None
        async for stream_event in stream_with_fallback(self.provider, request):
            if stream_event.type == "message_start":
                event = self.events.emit(
                    EventType.MODEL_STREAM_START,
                    {
                        "model": stream_event.payload.get("model", self.model),
                    },
                    parent_id=parent_id,
                )
                yield event, None
            elif stream_event.type == "text_delta":
                text = str(stream_event.payload.get("text", ""))
                text_parts.append(text)
                event = self.events.emit(
                    EventType.MODEL_TEXT_DELTA,
                    {"text": text},
                    parent_id=parent_id,
                )
                yield event, None
            elif stream_event.type == "message_stop":
                response_payload = stream_event.payload.get("response")
                if isinstance(response_payload, ModelResponse):
                    final_response = response_payload
                elif response_payload:
                    final_response = ModelResponse.model_validate(response_payload)
                else:
                    final_response = ModelResponse(
                        content=[TextBlock(text="".join(text_parts))],
                        stop_reason="end_turn",
                        model=self.model,
                    )

                stream_end = self.events.emit(
                    EventType.MODEL_STREAM_END,
                    {
                        "stop_reason": final_response.stop_reason,
                        "usage": final_response.usage.model_dump(),
                    },
                    parent_id=parent_id,
                )
                yield stream_end, None

                response_event = self._emit_model_response(
                    final_response, parent_id=parent_id
                )
                yield response_event, final_response
            elif stream_event.type == "error":
                message = str(stream_event.payload.get("error", "provider stream error"))
                event = self.events.emit(
                    EventType.ERROR,
                    {"stage": "model_stream", "error": message},
                    parent_id=parent_id,
                )
                yield event, None
                raise ProviderError(message)

        if final_response is None:
            raise ProviderError("Provider stream ended without message_stop")

    def _build_model_request(self) -> ModelRequest:
        tools_schema = [
            ToolSchema(
                name=tool.name,
                description=tool.description,
                input_schema=tool.parameters,
            )
            for tool in self.tools.values()
        ]
        return ModelRequest(
            model=self.model,
            messages=self.messages,
            tools=tools_schema,
            system=self.system,
        )

    def _emit_model_request(
        self, request: ModelRequest, parent_id: str | None
    ) -> Event:
        return self.events.emit(
            EventType.MODEL_REQUEST,
            {
                "model": request.model,
                "num_messages": len(request.messages),
                "num_tools": len(request.tools),
                "messages": [m.model_dump(mode="json") for m in request.messages],
                "system": request.system,
            },
            parent_id=parent_id,
        )

    def _emit_model_response(
        self, response: ModelResponse, parent_id: str | None
    ) -> Event:
        return self.events.emit(
            EventType.MODEL_RESPONSE,
            {
                "stop_reason": response.stop_reason,
                "text": response.text()[:500],
                "content": [b.model_dump(mode="json") for b in response.content],
                "tool_uses": [t.name for t in response.tool_uses()],
                "usage": response.usage.model_dump(),
            },
            parent_id=parent_id,
        )

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
        tool_uses = response.tool_uses()
        if self._can_execute_in_parallel(tool_uses):
            return await self._execute_parallel_tools(tool_uses, parent_id)

        tool_results: list[dict] = []

        for block in tool_uses:
            tool_results.append(await self._execute_one(block, parent_id))

        return tool_results

    def _can_execute_in_parallel(self, tool_uses: list[ToolUseBlock]) -> bool:
        """Return whether a batch contains only known read-only parallel tools."""
        if len(tool_uses) < 2:
            return False

        for block in tool_uses:
            tool = self.tools.get(block.name)
            if tool is None:
                return False
            if not tool.parallel_safe or tool.mutates_workspace:
                return False
        return True

    async def _execute_parallel_tools(
        self,
        tool_uses: list[ToolUseBlock],
        parent_id: str | None,
    ) -> list[dict]:
        """Execute a safe read-only tool batch concurrently with ordered results."""
        prepared: list[dict[str, Any]] = []

        for block in tool_uses:
            tool_use_id = block.id
            tool_name = block.name
            tool_input = block.input

            call_event = self.events.emit(
                EventType.TOOL_CALL_REQUESTED,
                {"tool": tool_name, "input": tool_input, "tool_use_id": tool_use_id},
                parent_id=parent_id,
            )

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
                prepared.append({
                    "block": block,
                    "result": self._error_result(tool_use_id, f"Tool blocked: {reason}"),
                })
                continue

            tool = self.tools.get(tool_name)
            if tool is None:
                prepared.append({
                    "block": block,
                    "result": self._error_result(
                        tool_use_id,
                        f"Tool not found: {tool_name}",
                    ),
                })
                continue

            self.events.emit(
                EventType.TOOL_START,
                {"tool": tool_name, "tool_use_id": tool_use_id},
                parent_id=call_event.id,
            )
            prepared.append({
                "block": block,
                "call_event": call_event,
                "task": asyncio.create_task(self._run_tool(tool, tool_input)),
            })

        tasks = [item["task"] for item in prepared if "task" in item]
        if tasks:
            await asyncio.gather(*tasks)

        tool_results: list[dict] = []
        for item in prepared:
            block = item["block"]
            if "result" in item:
                tool_results.append(item["result"])
                continue

            is_error, result, result_str = item["task"].result()
            self.extension_manager.fire_tool_result(block.name, result, is_error)
            self.events.emit(
                EventType.TOOL_END,
                {
                    "tool": block.name,
                    "tool_use_id": block.id,
                    "is_error": is_error,
                    "result": result_str[:500],
                },
                parent_id=item["call_event"].id,
            )
            if is_error:
                tool_results.append(self._error_result(block.id, result_str))
            else:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                    "is_error": False,
                })

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

        is_error, result, result_str = await self._run_tool(tool, tool_input)
        self.extension_manager.fire_tool_result(tool_name, result, is_error)
        self.events.emit(
            EventType.TOOL_END,
            {
                "tool": tool_name,
                "tool_use_id": tool_use_id,
                "is_error": is_error,
                "result": result_str[:500],
            },
            parent_id=call_event.id,
        )
        if is_error:
            return self._error_result(tool_use_id, result_str)
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": result_str,
            "is_error": False,
        }

    async def _run_tool(self, tool: Any, tool_input: dict) -> tuple[bool, Any, str]:
        """Execute a tool and normalize success/error values."""
        try:
            result = await tool.execute(**tool_input)
            return False, result, str(result)
        except Exception as exc:  # noqa: BLE001 - surface as tool error to model
            error_msg = f"Tool execution failed: {exc}"
            return True, error_msg, error_msg

    @staticmethod
    def _error_result(tool_use_id: str, message: str) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": message,
            "is_error": True,
        }
