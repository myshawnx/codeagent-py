# Design Decisions

This document explains the current architectural choices in OriCode.

## Positioning

OriCode is a Python-first, local-first coding-agent runtime. It is now mature enough to demonstrate the core infrastructure of a serious coding agent:

- provider abstraction
- safe local tools
- policy and approval flow
- event tracing
- session resume
- streaming
- evals
- MCP presets
- parallel safe tool execution
- read-result caching
- observability sinks

It is not positioned as a full commercial replacement for Claude Code, Codex, Cursor, or similar products. The project focuses on the runtime foundation, not product polish.

## Why Python

Python is the right fit for this project because most agent infrastructure, LLM SDKs, eval harnesses, and AI interview discussions are Python-first. The project still keeps strong typing through Pydantic models and type hints.

Trade-off: TypeScript has stronger compile-time ergonomics, but Python makes the runtime easier to discuss, test, and extend in AI-infrastructure contexts.

## Why Not LangChain

The goal is to show the mechanics of a coding agent, not to hide them behind a framework.

OriCode implements its own:

- model request / response normalization
- tool-calling loop
- policy gateway
- event stream
- session trace persistence
- eval runner

This makes the important agent-runtime decisions visible in code review.

## Provider Abstraction

The runtime depends on `ModelProvider`, not directly on Anthropic SDK response objects.

Current provider behavior:

- `AnthropicProvider` adapts the official async Anthropic SDK.
- `MockProvider` enables deterministic offline tests.
- token counting lives at the provider layer.
- unsupported token counting falls back to explicit estimated counts.
- streaming provider events are normalized before reaching the runtime.

This keeps the agent loop provider-neutral while allowing provider-specific accuracy where needed.

## Token Counting at the Provider Layer

Token counting is intentionally not hard-coded as `len(text) // 4` in the runtime.

The provider owns token counting because tokenization is provider-specific:

- Anthropic uses the official `messages.count_tokens` API.
- MockProvider can return fixed counts for tests.
- fallback counts are marked estimated.

The context builder can use provider-backed counts without knowing which provider is active.

## Streaming as Runtime Events

Streaming is modeled as provider-neutral stream events and runtime events.

The non-streaming and streaming paths both normalize to `ModelResponse`, so the runtime does not grow two incompatible control flows. CLI `--stream` is a user-facing consumer of the same event model that future UI layers could consume.

## Event Stream and Event Sinks

`EventBus` is the runtime's observable fact stream. It records lifecycle events such as:

- session start / end
- model request / response
- model stream deltas
- tool call requested
- policy verdict
- approval request / decision
- tool start / end
- errors

Event sinks keep observability outside the agent loop:

- `InMemorySink` for tests and embedded callers
- `ConsoleSink` for local debugging
- `TraceWriter` for JSONL persistence

This keeps tracing, evals, debugging, and future telemetry aligned around the same data.

## JSONL Session Traces

JSONL was chosen over SQLite because traces should be:

- append-friendly
- human-readable
- easy to diff
- easy to inspect with basic shell tools

Current traces include enough normalized model request / response content to support linear resume. Fork/tree session history is intentionally future work.

## Linear Resume Before Fork Trees

The project implements linear resume first:

```bash
oricode resume <session-id> "continue from here"
```

This reconstructs normalized messages from JSONL events and appends a new user prompt. It does not attempt to restore running tools, external processes, or concurrent state. That narrower scope is deliberate and reliable.

## Two Layers of Safety

Safety is split into two independent layers:

1. Policy layer: user-configurable allow / confirm / deny decisions.
2. Tool layer: hard workspace boundaries and execution limits.

This defense-in-depth design means path traversal, symlink escapes, and absolute path escapes are blocked even if policy configuration is incomplete.

## Approval Outside the Policy Engine

The policy engine remains a pure classifier. It returns `allow`, `confirm`, or `deny`.

The `PolicyGateway` handles side effects:

- emits policy and approval events
- calls an `ApprovalHandler`
- blocks denied confirmations

Implemented handlers include:

- auto approval for `auto` mode and tests
- non-interactive deny for print / CI-style runs
- Rich prompt approval for local CLI use
- recording handler for tests and evals

This keeps UI concerns out of the policy engine.

## Parallel Tool Execution

Only explicitly marked read-only tools can run concurrently. Current built-ins:

- `read`: parallel safe
- `git_diff`: parallel safe
- `write`, `edit`, `apply_patch`, `bash`: serialized

The runtime preserves deterministic result ordering even when safe tools run in parallel. Mutating tools remain serialized.

## Read Tool Cache

The read cache is intentionally narrow:

- only caches `read`
- validates entries with `mtime_ns` and file size
- invalidates a path after `write`, `edit`, and `apply_patch`
- clears all cached reads after `bash`

This captures the common repeated-read optimization without building a risky generic tool cache.

## Eval Harness as a First-Class Runtime Consumer

The eval system is deliberately lightweight but meaningful:

- YAML scenarios
- isolated temporary workspaces
- expected and forbidden file checks
- structured metrics
- post-run test commands
- markdown / JSON reports
- per-scenario trace export

The point is not leaderboard benchmarking. The point is to demonstrate how the agent can be regression-tested.

## MCP Presets

MCP support is implemented as stdio JSON-RPC integration plus configuration helpers.

Current presets:

- `filesystem`
- `github`

Secrets are not written into `.agent/mcp.json`; presets use environment placeholders such as `${GITHUB_TOKEN}`.

Remaining MCP work is product-level hardening: health checks, broader curated presets, better credential UX, and marketplace-like lifecycle management.

## What Is Still Out of Scope

These are intentionally not productionized yet:

- polished TUI / IDE integration
- hosted sandboxing or container isolation
- fork/tree session model
- SDK/RPC parity with commercial agent CLIs
- multi-agent orchestration
- production auth, billing, and rate limiting
- OpenTelemetry exporter
- broader MCP marketplace lifecycle

## Summary

OriCode is designed to be:

- testable: `165 passed, 4 skipped`
- safe: policy plus tool-level hard boundaries
- observable: EventBus, EventSink, JSONL traces
- resumable: linear JSONL trace reconstruction
- provider-neutral: normalized provider protocol
- extensible: extension hooks and MCP integration

That is the right level of completeness for a local-first coding-agent runtime and an interview-grade systems project.
