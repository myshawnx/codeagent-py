# OriCode Demo Guide

This guide is a concise walkthrough for presenting OriCode as a mature local coding-agent runtime.

## Setup

```bash
uv sync
uv run oricode init
export ANTHROPIC_API_KEY=your-key-here
```

For offline architecture demos, use the test suite instead of real model calls.

## Demo 1: Project Positioning

Open [README.md](README.md) and start with the "Current Maturity" section.

Key message:

> OriCode is runtime-complete for interview and architecture discussion, but not a polished commercial coding-assistant product.

It has the core runtime layers:

- provider abstraction
- safe tools
- policy and approval
- streaming
- traces and resume
- evals
- MCP presets
- parallel safe tools
- read cache
- observability sinks

## Demo 2: Offline Agent Loop

Run the full offline loop tests:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_events.py -q
```

Show:

- `MockProvider` scripts model responses.
- The loop executes tool calls without an API key.
- tool results are fed back as normalized `tool_result` blocks.
- policy-blocked tools are tested offline.

Best file to open:

```text
tests/unit/test_events.py
```

## Demo 3: Safe Local Tools

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_tool_safety.py -q
```

What to explain:

- `resolve_in_workspace()` blocks parent traversal, absolute escapes, and symlink escapes.
- file tools enforce size and ambiguity checks.
- bash has timeout and output truncation.
- read results are cached and invalidated after writes.

Best files:

```text
src/oricode/runtime/tools.py
src/oricode/util/workspace.py
tests/unit/test_tool_safety.py
```

## Demo 4: Policy and Approval

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_policy.py -q
```

Show:

- `policy/engine.py` is pure and deterministic.
- `PolicyGateway` handles runtime side effects.
- approval handlers turn `confirm` verdicts into actual decisions.
- approval request and decision events are emitted.

Best files:

```text
src/oricode/policy/engine.py
src/oricode/policy/gateway.py
src/oricode/policy/approval.py
```

## Demo 5: Streaming Runtime

Run streaming tests:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_events.py::TestOfflineAgentLoop::test_streaming_text_response -q
```

Then show CLI support:

```bash
uv run oricode ask "summarize this project" --stream
```

Talking point:

Streaming is normalized into runtime events and still ends in a normal `ModelResponse`.

## Demo 6: Traces and Resume

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_trace.py -q
```

CLI flow:

```bash
uv run oricode sessions
uv run oricode sessions <session-id>
uv run oricode resume <session-id> "continue from here"
```

Talking point:

JSONL traces are not just logs. They contain enough normalized model request / response data to reconstruct conversation history for linear resume.

## Demo 7: Eval Harness

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_eval.py -q
```

CLI examples:

```bash
uv run oricode eval --benchmark simple_edit
uv run oricode eval --benchmark security
uv run oricode eval --benchmark test_driven_fix
uv run oricode eval --benchmark all --no-save-traces
```

Show:

- YAML scenarios
- expected files
- forbidden files
- post-run tests
- structured metrics
- markdown / JSON reports
- per-scenario traces under `.agent/eval-traces`

Best files:

```text
src/oricode/eval/
src/oricode/eval/benchmarks/
tests/unit/test_eval.py
```

## Demo 8: MCP Presets

Run:

```bash
uv run oricode mcp presets
uv run oricode mcp add filesystem
uv run oricode mcp list
```

For GitHub:

```bash
export GITHUB_TOKEN=...
uv run oricode mcp add github
```

Talking point:

MCP integration is a practical baseline: stdio JSON-RPC, config file, filesystem/GitHub presets, and environment-based credential placeholders. It is not yet a full marketplace.

## Demo 9: Parallel Safe Tools and Cache

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_events.py::TestOfflineAgentLoop::test_parallel_safe_tools_execute_concurrently_in_order -q
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_tool_safety.py::TestFileToolHardening::test_write_tool_invalidates_read_cache_for_same_size_content -q
```

Talking point:

Only explicitly marked read-only tools can run concurrently. Mutating tools remain serialized, and read cache invalidation keeps repeated reads safe.

## Demo 10: Observability Sinks

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_events.py::TestEventBus::test_subscribe_sink_receives_events -q
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_trace.py::TestTraceWriterRoundTrip::test_trace_writer_implements_sink_write -q
```

Talking point:

`EventBus` emits the facts. `EventSink` decides where they go: memory, console, JSONL, and future telemetry exporters.

## Full Verification

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

Expected:

```text
165 passed, 4 skipped
```

## Interview Talking Points

### How do you avoid vendor lock-in?

The runtime uses `ModelProvider` and normalized request / response types. Anthropic is an adapter; MockProvider is another adapter for offline tests.

### How do you avoid runaway agents?

Loop guards track tool calls, token budgets, repeated failures, and reward-hacking behavior such as modifying test files in a repair task.

### How do you make local tools safe?

Policy gates decide allow / confirm / deny, while tools enforce workspace boundaries and execution limits regardless of policy.

### How do you debug agent behavior?

Every important runtime step emits a structured event. JSONL traces can be inspected, replayed for resume, or exported from evals.

### How do you evaluate an agent?

YAML scenarios define inputs, expected outputs, forbidden files, and post-run tests. Reports include structured metrics and traces.

## Honest Limitations

Still future work:

- polished TUI / IDE integration
- fork/tree sessions
- hosted sandboxing
- broader MCP server lifecycle
- OpenTelemetry exporter
- SDK/RPC surface
- multi-agent orchestration

Final message:

> OriCode is a complete local coding-agent runtime foundation. It is serious architecture, tested offline, and honest about what remains product/platform scope.
