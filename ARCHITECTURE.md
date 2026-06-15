# CodeAgent-Py Architecture

## Overview

CodeAgent-Py is a Python-first local coding-agent runtime. It is organized around a small set of explicit layers:

```text
CLI
  -> AgentSession
    -> Context Builder
    -> AgentLoop
      -> ModelProvider
      -> Tool Registry
      -> ExtensionManager
        -> PolicyGateway
        -> LoopGuards
        -> MCPExtension
      -> EventBus
        -> EventSink
        -> TraceWriter
```

The key idea is separation of concerns:

- providers normalize model APIs
- the loop coordinates model/tool turns
- tools enforce hard local safety
- extensions enforce policy and guardrails
- events record observable facts
- traces make sessions inspectable and resumable
- evals consume the same runtime as real sessions

## Main Components

### CLI Layer

Implemented with Typer and Rich.

Commands:

```bash
codeagent init
codeagent ask "..."
codeagent ask "..." --stream
codeagent resume <session-id> "..."
codeagent sessions
codeagent sessions <session-id>
codeagent eval --benchmark all
codeagent mcp list
codeagent mcp presets
codeagent mcp add filesystem
codeagent mcp add github
```

### Session Layer

`AgentSession` owns:

- working directory
- model provider
- built-in tools
- extension manager
- event bus
- system prompt
- optional initial messages for resume

It is responsible for building the runtime environment and starting / ending a session.

### Context Layer

The context builder loads:

- base system prompt
- detected project profile
- project instructions from `.agent/instructions.md`, `AGENTS.md`, or `CLAUDE.md`
- provider-backed token budgets when available

Token counting is provider-level, not hard-coded in the context builder.

### Provider Layer

The runtime depends on `ModelProvider`.

Current providers:

- `AnthropicProvider`
- `MockProvider`

Provider responsibilities:

- generate normalized `ModelResponse`
- stream normalized `ModelStreamEvent`
- count tokens when supported
- normalize provider-specific errors

### Runtime Loop

`AgentLoop` drives the conversation:

1. append user prompt
2. build `ModelRequest`
3. call provider
4. emit model events
5. execute tool calls if requested
6. append tool results
7. continue until terminal response

The runtime supports:

- standard `run()`
- streaming `run_stream()`
- parallel execution for safe read-only tool batches
- deterministic result ordering

### Tool Layer

Built-in tools:

| Tool | Mutates workspace | Parallel safe |
|---|---:|---:|
| `read` | No | Yes |
| `git_diff` | No | Yes |
| `write` | Yes | No |
| `edit` | Yes | No |
| `apply_patch` | Yes | No |
| `bash` | Yes by default | No |

Tool hardening:

- workspace path resolution
- parent traversal blocking
- absolute escape blocking
- symlink escape blocking
- file size limits
- edit ambiguity checks
- bash timeout
- output truncation

The `read` tool uses a narrow cache validated by `mtime_ns` and size. Writes invalidate affected paths; bash clears the cache.

### Extension Layer

Extensions receive session and tool lifecycle hooks:

```python
class Extension:
    def on_session_start(self, api): ...
    def on_tool_call(self, api, tool_name, tool_input): ...
    def on_tool_result(self, api, tool_name, result, is_error): ...
    def on_message_end(self, api, usage): ...
    def on_session_end(self, api): ...
```

Current extensions:

- `PolicyGateway`
- `LoopGuardsExtension`
- `MCPExtension`

### Policy and Approval

The policy engine is pure:

```python
classify(event, mode, policy, opts) -> AllowVerdict | ConfirmVerdict | DenyVerdict
```

The gateway handles runtime effects:

- appends policy entries
- emits policy events
- routes confirmations through an approval handler
- blocks denied calls

Approval handlers:

- `AutoApprovalHandler`
- `DenyApprovalHandler`
- `RichPromptApprovalHandler`
- `RecordingApprovalHandler`

### Loop Guards

Loop guards protect against:

- too many tool calls
- token budget exhaustion
- repeated failures
- reward hacking by editing tests during repair tasks

### MCP Layer

MCP support is a practical stdio JSON-RPC baseline.

Current pieces:

- `MCPClient`
- `MCPToolAdapter`
- `MCPExtension`
- `.agent/mcp.json`
- presets for `filesystem` and `github`

Credential handling uses environment placeholders such as `${GITHUB_TOKEN}` rather than storing secrets in config files.

### Event and Observability Layer

`EventBus` records lifecycle events in memory and notifies listeners.

Important event types:

- `session_start`
- `turn_start`
- `model_request`
- `model_stream_start`
- `model_text_delta`
- `model_stream_end`
- `model_response`
- `tool_call_requested`
- `policy_verdict`
- `approval_requested`
- `approval_decision`
- `tool_start`
- `tool_end`
- `turn_end`
- `session_end`
- `error`

Event sinks:

- `InMemorySink`
- `ConsoleSink`
- `TraceWriter`

This keeps observability decoupled from the agent loop.

### Trace and Resume Layer

Traces are written as JSONL:

```text
.agent/sessions/<session_id>.jsonl
```

Trace files are used for:

- debugging
- session inspection
- eval trace export
- linear resume

Resume reconstructs normalized conversation messages from model request / response and tool events, then appends a new user prompt.

### Eval Layer

The eval harness runs scenarios in temporary workspaces.

Features:

- YAML scenario files
- expected files
- forbidden files
- post-run test commands
- structured metrics
- markdown / JSON reports
- per-scenario JSONL traces

Built-in benchmark groups:

- `simple_edit`
- `security`
- `multi_file_refactor`
- `test_driven_fix`
- `instructions`

## Data Flow: `ask`

```text
User prompt
  -> CLI parses mode / stream flag
  -> load config
  -> choose approval handler
  -> load MCP config
  -> create AgentSession
  -> attach TraceWriter sink
  -> AgentLoop
    -> provider request
    -> provider response / stream events
    -> policy gateway
    -> tool execution
    -> loop guards
    -> final response
  -> trace persisted
```

## Data Flow: Tool Call

```text
tool_use block
  -> TOOL_CALL_REQUESTED event
  -> ExtensionManager.fire_tool_call()
    -> PolicyGateway.classify()
    -> optional ApprovalHandler
    -> LoopGuardsExtension
  -> POLICY_VERDICT event
  -> if allowed:
       TOOL_START
       execute tool
       TOOL_END
  -> if blocked:
       tool_result error
  -> model receives tool_result
```

## Data Flow: Resume

```text
session id
  -> find .agent/sessions/<id>.jsonl
  -> read trace
  -> reconstruct normalized messages
  -> create AgentSession(initial_messages=...)
  -> append new prompt
  -> continue loop
```

## Safety Model

CodeAgent-Py uses defense in depth:

1. policy classification
2. approval handlers
3. loop guards
4. tool-level path safety
5. tool-level size / timeout limits
6. traceability through events

No single layer is trusted as the only protection.

## Current Verification

```text
165 passed, 4 skipped
```

## Known Architecture Boundaries

Not currently implemented:

- fork/tree session graph
- hosted sandboxing
- polished TUI / IDE UI
- full MCP marketplace lifecycle
- SDK/RPC server surface
- OpenTelemetry exporter
- multi-agent orchestration

These are product/platform extensions on top of the current runtime foundation.
