# OriCode Project Summary

## Current Status

OriCode is now a mature **Python-first, local-first coding-agent runtime**.

It is complete enough to demonstrate the major runtime layers behind modern coding agents:

- provider abstraction
- agent loop
- normalized tool calling
- safe local tool execution
- policy and approvals
- runtime events
- JSONL tracing and resume
- streaming
- evals
- MCP presets
- parallel read-only tools
- read-result cache
- event sinks

It should be described as **runtime-complete for interview and architecture review**, not as a polished commercial coding-assistant product.

## Verification

Current expected test result:

```text
165 passed, 4 skipped
```

The skipped tests are integration-style tests that require real credentials or environment setup. The main runtime is covered by deterministic offline tests.

## Repository Snapshot

```text
src/oricode/
├── cli/            Typer CLI commands
├── config/         Pydantic config models and loaders
├── context/        project instructions, memory, profile, prompt building
├── eval/           YAML eval harness, benchmarks, reports, metrics
├── loop/           loop guards and reward-hacking protection
├── mcp/            stdio MCP client, extension, presets
├── policy/         pure policy engine, gateway, approval handlers
├── providers/      provider protocol, Anthropic adapter, MockProvider
├── runtime/        AgentSession, AgentLoop, tools, events, extensions
├── trace/          JSONL trace persistence and resume reconstruction
└── util/           workspace path safety helpers
```

## Implemented Capabilities

| Area | Status | Notes |
|---|---:|---|
| Provider abstraction | Complete | Runtime uses normalized provider types, not SDK objects |
| Anthropic provider | Complete | Async adapter with normalized responses |
| Mock provider | Complete | Scriptable offline provider for tests and evals |
| Provider token counting | Complete | Anthropic official count API; fallback counts marked estimated |
| Streaming | Complete | Provider-neutral stream events and CLI `--stream` |
| Tool calling | Complete | Normalized `tool_use` / `tool_result` blocks |
| Local tools | Complete | `read`, `write`, `edit`, `apply_patch`, `git_diff`, `bash` |
| Tool safety | Complete | Workspace boundaries, symlink escape blocking, size limits |
| Bash hardening | Complete | Timeout, output truncation, nonzero exit handling |
| Policy engine | Complete | Pure allow / confirm / deny classifier |
| Approval handlers | Complete | Auto, deny, Rich prompt, recording handler |
| Loop guards | Complete | Tool limits, token budget, repeated failure guard, test-file anti-cheat |
| Session traces | Complete | `.agent/sessions/<session_id>.jsonl` |
| Resume | Complete | Linear resume from JSONL trace |
| Eval harness | Complete | Richer benchmarks, structured metrics, trace export |
| MCP integration | Practical baseline | stdio client, extension, filesystem/GitHub presets |
| Parallel safe tools | Complete | read-only batches execute concurrently with ordered results |
| Tool result cache | Complete | read cache with mtime/size validation and write invalidation |
| Observability sinks | Complete | EventSink protocol, in-memory, console, JSONL trace sink |

## CLI Commands

```bash
uv run oricode init
uv run oricode ask "inspect this repo" --mode readonly
uv run oricode ask "fix the issue" --stream
uv run oricode resume <session-id> "continue from here"
uv run oricode sessions
uv run oricode sessions <session-id>
uv run oricode eval --benchmark all
uv run oricode eval --benchmark all --no-save-traces
uv run oricode mcp list
uv run oricode mcp presets
uv run oricode mcp add filesystem
uv run oricode mcp add github
```

## Why The Project Is Strong Now

The project demonstrates senior agent-runtime judgment:

- separates provider adapters from runtime logic
- keeps policy pure and UI decisions outside the classifier
- tests the agent loop offline without API calls
- records enough event data to debug, eval, and resume sessions
- treats evals as first-class, not an afterthought
- applies defense-in-depth around local tools
- keeps product-scope limits explicit

## Remaining Gaps

These gaps are mostly product/platform scope, not missing runtime fundamentals:

- polished TUI / IDE integration
- fork/tree session model
- hosted sandbox or container isolation
- broader MCP marketplace and health checks
- SDK/RPC parity
- multi-agent orchestration
- production auth, billing, rate limiting
- OpenTelemetry exporter

## Final Assessment

Yes: OriCode is now a well-rounded coding-agent runtime.

The best one-line positioning is:

> OriCode is a Python-first, local-first, testable, observable, policy-aware coding-agent runtime that demonstrates the core architecture behind production coding agents while staying honest about product-scope boundaries.
