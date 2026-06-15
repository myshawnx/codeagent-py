# OriCode Improvement Summary

## Executive Summary

OriCode has been upgraded from a functional prototype into a mature local coding-agent runtime.

Current verification:

```text
165 passed, 4 skipped
```

The project now demonstrates the core architecture expected in a serious coding agent:

- provider-neutral model runtime
- accurate provider-level token counting
- streaming and non-streaming model execution
- normalized tool calling
- safe local tools
- policy and approval handling
- loop guards
- JSONL traces
- linear resume
- deterministic evals
- MCP presets
- parallel safe tools
- read-result cache
- event sinks for observability

## Before

The original version had several important limitations:

- runtime coupled directly to Anthropic SDK response shapes
- weak offline testing story
- limited event model
- no provider-level token counting
- no streaming runtime
- session traces not yet useful for resume
- confirm verdicts did not route through real approval handlers
- eval suite was thin
- MCP support was mostly a skeleton
- tool execution was serial
- repeated reads had no cache
- observability was tied directly to in-memory event collection

## After

The current version has a layered runtime that is easier to test, inspect, and extend:

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

## Delivered Improvements

### P0: Provider-Level Token Counting

Implemented provider-owned token counting:

- `ModelProvider.count_tokens()`
- Anthropic official `messages.count_tokens`
- MockProvider deterministic token counts
- fallback counts marked as estimated
- context builder can use provider-backed counts

Why it matters: context budgeting is provider-specific and should not be guessed in the runtime.

### P1: Streaming Runtime

Implemented provider-neutral streaming:

- `ModelProvider.stream()`
- normalized `ModelStreamEvent`
- runtime `run_stream()`
- CLI `--stream`
- stream errors emitted as runtime events
- final streaming responses normalize back to `ModelResponse`

Why it matters: streaming improves UX without splitting the runtime into two incompatible paths.

### P2: Linear Resume

Implemented trace-based resume:

- reconstruct messages from JSONL trace events
- `oricode resume <session-id> "prompt"`
- corrupted trace safety handling
- resume tests showing history is sent back to provider

Scope boundary: this is linear resume, not fork/tree session management.

### P3: Interactive Approval Handlers

Implemented approval routing outside the pure policy engine:

- `ApprovalHandler` protocol
- `AutoApprovalHandler`
- `DenyApprovalHandler`
- `RichPromptApprovalHandler`
- `RecordingApprovalHandler`
- approval request / decision events
- non-interactive deny in print-style usage

Why it matters: policy remains deterministic while UI and CI behavior can vary safely.

### P4: Richer Eval System

Expanded evals into a stronger hiring signal:

- `multi_file_refactor`
- `test_driven_fix`
- `instructions`
- structured `EvalMetrics`
- expected / forbidden file checks
- post-run test commands
- dangerous operation blocking metrics
- per-scenario JSONL trace export
- richer markdown / JSON reports

Why it matters: the project can regress-test agent behavior, not just demonstrate it manually.

### P5: MCP Preset Configuration

Implemented practical MCP configuration:

- `.agent/mcp.json`
- `oricode mcp presets`
- `oricode mcp add filesystem`
- `oricode mcp add github`
- env placeholder credential handling such as `${GITHUB_TOKEN}`
- automatic MCP extension loading in `ask` and `resume`
- legacy config compatibility

Scope boundary: not a full MCP marketplace or health-checking lifecycle.

### P6: Parallel Safe Tools

Implemented conservative parallel tool execution:

- `Tool.parallel_safe`
- `Tool.mutates_workspace`
- `read` and `git_diff` can run concurrently
- mutating tools remain serialized
- result order remains deterministic

Why it matters: performance improves where safe, without risking write races.

### P7: Read Tool Cache

Implemented a narrow, safe read cache:

- caches only `read`
- validates with `mtime_ns` and file size
- invalidates path after `write`, `edit`, `apply_patch`
- clears cache after `bash`
- preserves workspace path safety

Why it matters: repeated tool reads can be cheaper without introducing a broad stale-cache problem.

### P8: Event Sinks

Implemented observability sink abstraction:

- `EventSink` protocol
- `InMemorySink`
- `ConsoleSink`
- `TraceWriter.write(event)`
- `EventBus.subscribe_sink()`

Why it matters: tracing, console debugging, tests, and future telemetry can share one event stream.

## Current Test Result

```text
165 passed, 4 skipped
```

Important covered areas:

- provider normalization
- token counting
- streaming
- offline agent loop
- policy classification
- approval handling
- tool safety
- symlink and path escape blocking
- bash hardening
- JSONL tracing
- linear resume
- eval metrics
- MCP preset config
- parallel safe tool execution
- read cache invalidation
- event sinks

## Current Positioning

OriCode is now best described as:

> A Python-first, local-first, testable, observable, policy-aware coding-agent runtime.

It is complete enough for architecture review and interview demonstration. It is still intentionally smaller than Claude Code, Codex, Cursor, and similar commercial coding-agent products.

## Remaining Work

Future improvements are mostly product/platform additions:

- fork/tree sessions
- richer TUI / IDE UX
- container or OS-level sandboxing
- OpenTelemetry exporter
- MCP health checks and broader preset catalog
- SDK/RPC surface
- multi-agent orchestration
- production auth and rate limiting

## Final Assessment

The core coding-agent runtime is now in strong shape. The project clearly demonstrates how to build, test, observe, and safely control a local coding agent.
