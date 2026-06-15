# OriCode Interview Showcase

## One-Line Pitch

OriCode is a Python-first, local-first coding-agent runtime that demonstrates the core infrastructure behind production coding agents: provider abstraction, tool calling, policy control, safe local execution, traces, resume, evals, MCP integration, parallel safe tools, caching, and observability.

## Current Proof Point

```text
165 passed, 4 skipped
```

The important point is not just the number. The suite exercises the runtime offline through `MockProvider`, so the core agent loop can be tested without spending API credits.

## Why This Is A Strong Coding-Agent Project

Most small agent demos are:

```text
prompt -> model -> maybe tool -> print
```

OriCode is structured like infrastructure:

```text
ModelProvider
AgentLoop
Tool Registry
PolicyGateway
ApprovalHandler
LoopGuards
EventBus
TraceWriter
EvalHarness
MCPExtension
```

That makes it useful for interview discussions about real agent systems.

## Best Demo Path

### 1. Provider Abstraction

Show:

```text
src/oricode/providers/types.py
src/oricode/providers/base.py
src/oricode/providers/anthropic_provider.py
src/oricode/providers/mock_provider.py
```

Talking point:

The runtime never depends directly on Anthropic SDK response objects. It depends on normalized `ModelRequest`, `ModelResponse`, `ToolUseBlock`, and `TextBlock` types.

### 2. Offline Runtime Test

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_events.py::TestOfflineAgentLoop -q
```

Talking point:

MockProvider scripts model behavior, so full tool-use loops can be tested without an API key.

### 3. Tool Safety

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_tool_safety.py -q
```

Talking point:

Safety is enforced twice:

- policy layer decides allow / confirm / deny
- tool layer enforces hard workspace boundaries

Even if policy is wrong, tools block path traversal and symlink escapes.

### 4. Policy and Approval

Show:

```text
src/oricode/policy/engine.py
src/oricode/policy/gateway.py
src/oricode/policy/approval.py
```

Talking point:

The policy engine is pure. The gateway performs side effects and delegates confirmations to approval handlers.

### 5. Streaming

Show:

```text
src/oricode/providers/types.py
src/oricode/runtime/loop.py
src/oricode/cli/commands/ask.py
```

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_events.py::TestOfflineAgentLoop::test_streaming_text_response -q
```

Talking point:

Streaming is normalized into runtime events and still produces a final normalized response.

### 6. Traces and Resume

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_trace.py -q
```

CLI:

```bash
uv run oricode sessions
uv run oricode resume <session-id> "continue from here"
```

Talking point:

JSONL traces are not only logs. They are structured enough to reconstruct conversation history for linear resume.

### 7. Eval Harness

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_eval.py -q
```

Show:

```text
src/oricode/eval/benchmarks/
src/oricode/eval/types.py
src/oricode/eval/harness.py
```

Talking point:

The eval harness treats agent behavior as something that can be regression-tested. It tracks expected files, forbidden files, post-run tests, tool calls, tokens, duration, and dangerous operation blocking.

### 8. MCP Presets

Run:

```bash
uv run oricode mcp presets
uv run oricode mcp add filesystem
uv run oricode mcp list
```

Talking point:

The project supports stdio MCP integration and practical presets, while keeping secrets in environment variables rather than config files.

### 9. Parallel Safe Tools

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_events.py::TestOfflineAgentLoop::test_parallel_safe_tools_execute_concurrently_in_order -q
```

Talking point:

Only read-only tools marked `parallel_safe` can run concurrently. Mutating tools are serialized.

### 10. Observability Sinks

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_events.py::TestEventBus::test_subscribe_sink_receives_events -q
```

Talking point:

`EventBus` is the fact stream; sinks decide where events go. That makes JSONL traces, console debugging, tests, and future telemetry share one path.

## Interview Q&A

### How do you avoid vendor lock-in?

By using a `ModelProvider` protocol and normalized model types. Anthropic-specific code lives in `AnthropicProvider`; tests use `MockProvider`.

### How do you handle token budgets?

Token counting is provider-level. Anthropic uses the official count API, MockProvider uses deterministic values, and fallback counts are marked estimated.

### How do you make the agent safe locally?

Policy controls user-configurable risk. Tools enforce hard boundaries. Loop guards add resource and reward-hacking protection.

### How do you debug a failed run?

Inspect the JSONL trace. It contains model requests, responses, tool calls, policy verdicts, approvals, errors, and session lifecycle events.

### How do you resume a session?

`oricode resume` reads JSONL trace events, reconstructs normalized messages, appends a new prompt, and continues the loop.

### How do you evaluate the agent?

Use YAML eval scenarios. They define input files, expected files, forbidden files, post-run tests, and scoring metrics.

### Is it production-ready?

It is runtime-complete for a local single-user agent and strong as an interview artifact. It is not a full commercial product because it does not include polished UI, cloud sandboxing, production auth, fork/tree sessions, or a full MCP marketplace.

## Current Strengths

- small enough to review
- testable offline
- provider-neutral
- policy-aware
- observable
- resumable
- eval-driven
- local-first
- honest about scope

## Remaining Product Work

- TUI / IDE UX
- fork/tree session model
- sandbox/container execution
- OpenTelemetry exporter
- MCP health checks and broader presets
- SDK/RPC surface
- multi-agent workflows

## Closing Line

This project shows that I understand the runtime mechanics behind coding agents, not just how to call an LLM API.
