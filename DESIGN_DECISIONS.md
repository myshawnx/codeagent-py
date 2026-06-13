# Design Decisions

This document explains the architectural choices made in CodeAgent-Py and the reasoning behind them.

---

## Why Python?

**Decision**: Implement the agent in Python rather than TypeScript (the original agent-cli).

**Reasoning**:
- **AI/ML ecosystem**: Most agent frameworks, LLM libraries, and tooling are Python-first (LangChain, LlamaIndex, Anthropic SDK, etc.)
- **Target audience**: The interview is for an AI agent role — Python is the expected language
- **Simplicity**: Python's async/await is cleaner for LLM I/O patterns
- **Portability**: Easier to run in notebooks, cloud functions, and research environments

**Trade-off**: TypeScript has better type safety and LSP support, but Python's Pydantic + type hints are sufficient for this scope.

---

## Why NOT LangChain?

**Decision**: Build a custom agent loop instead of using LangChain or LlamaIndex.

**Reasoning**:
- **Interview goal**: Demonstrate understanding of agent runtime architecture, not framework integration
- **Complexity**: LangChain adds 50+ dependencies and abstractions that obscure the core loop
- **Control**: Custom loop gives full control over policy enforcement, event emission, and error handling
- **Testability**: MockProvider makes the loop 100% testable offline; LangChain's abstractions make this harder

**What we borrowed**: The concept of a tool-calling loop, structured tool schemas, and extension hooks are industry-standard patterns (not LangChain-specific).

---

## Provider Abstraction Layer

**Decision**: Decouple the runtime from the Anthropic SDK with a `ModelProvider` protocol.

**Reasoning**:
- **Vendor lock-in**: Tight coupling to Anthropic's SDK response objects is fragile
- **Testability**: MockProvider lets us test the full loop offline (40+ tests with zero API calls)
- **Portability**: Adding OpenAI/Google/etc. = 1 new adapter, not a runtime rewrite
- **Production pattern**: All production agent systems abstract providers (e.g., LiteLLM, OpenRouter)

**Implementation**:
- Normalized types: `ModelRequest`, `ModelResponse`, `TextBlock`, `ToolUseBlock`
- Provider protocol: `async def generate(request) -> response`
- Adapters: `AnthropicProvider`, `MockProvider`

**Trade-off**: Adds a thin layer of indirection, but the benefits (testability, portability) far outweigh the cost.

---

## Event Stream as Single Source of Truth

**Decision**: Emit structured events for every lifecycle step instead of ad-hoc logging.

**Reasoning**:
- **Observability**: Tracing, debugging, and evals all need the same data
- **Consistency**: One event model beats 3 different logging systems
- **Future-proof**: Events can power UIs, telemetry, and session replay without changing the loop

**Implementation**:
- Lightweight event model: `Event(type, payload, timestamp, session_id)`
- EventBus collects events + supports live listeners
- TraceWriter streams events to JSONL for persistence

**Inspired by**: Pi Agent's trajectory logs, but simplified (no branching, no LLM compaction yet).

---

## Two Layers of Safety: Policy + Tools

**Decision**: Enforce safety at both the policy layer (deny/confirm globs) AND the tool layer (workspace boundary checks).

**Reasoning**:
- **Defense in depth**: If policy has a bug, tools still prevent escape
- **Clear responsibility**: Policy = user-configurable rules; Tools = hard boundaries
- **Fail-safe**: Path traversal is NEVER allowed, even if policy misconfigured

**Implementation**:
- Tool layer: `resolve_in_workspace()` prevents `../`, symlinks, absolute paths
- Policy layer: `PolicyGateway` checks globs, command patterns, file change limits

**Trade-off**: Some redundancy, but safety is worth it.

---

## JSONL for Session Traces

**Decision**: Use JSONL (one JSON object per line) for trace persistence, not SQLite.

**Reasoning**:
- **Simplicity**: JSONL is human-readable, grep-able, and git-friendly
- **Streaming**: Events can be written as they occur (no transaction overhead)
- **Tooling**: Standard JSON parsers work; no schema migrations

**Trade-off**: Complex queries (find all tool calls across sessions) are slower than SQL, but that's not a current requirement.

**Future**: If we need rich queries, JSONL can be imported into DuckDB or SQLite on demand.

---

## No Context Compaction (Yet)

**Decision**: Context builder trims by character count, not LLM-based summarization.

**Reasoning**:
- **Scope control**: LLM compaction is complex (token counting, summarization, prompt injection risks)
- **Good enough**: For interview demos, character-based trimming + user instructions work fine
- **Future work**: When context becomes a bottleneck, add tiktoken-based trimming or LLM summarization

**Implementation**: `build_system_prompt(max_tokens=N)` does char-based approximation (4 chars/token).

---

## Pure-Function Policy Engine

**Decision**: Policy engine (`classify()`) is a pure function with no side effects.

**Reasoning**:
- **Testability**: Pure functions are trivial to test (57 policy tests, all passing)
- **Determinism**: Same input = same output, always
- **Composability**: Can be used in policy gateway, evals, or standalone tools

**Inspired by**: Functional programming principles (Haskell, Elm) — keep effects at the edges.

---

## Async-First Runtime

**Decision**: Use `AsyncAnthropic` and `async def` throughout the runtime, not sync wrappers.

**Reasoning**:
- **Correctness**: The original runtime had blocking calls inside `async def`, which is an anti-pattern
- **Future concurrency**: Async enables parallel tool calls, streaming responses, etc.
- **Industry standard**: All modern LLM APIs are async (OpenAI, Google, Anthropic)

**Implementation**:
- `AnthropicProvider` wraps `AsyncAnthropic` with timeout
- Tools are `async def` (even if they don't await, for consistency)
- Session.run() is `async def`, called via `asyncio.run()`

---

## What We Borrowed from Pi Agent

**Acknowledged inspiration**:
- **Trajectory logs**: Pi Agent's event-based session tracking → our EventBus
- **Tool safety**: Pi's path restrictions → our `resolve_in_workspace()`
- **Pure-function policy**: Pi's functional approach → our `classify()`

**What we changed**:
- No branching/forking (out of scope for this project)
- JSONL instead of Pi's custom format
- MockProvider instead of Pi's test harness

---

## What We Borrowed from Claude Code

**Acknowledged inspiration**:
- **System prompt**: Our `DEFAULT_SYSTEM_PROMPT` is inspired by Claude Code's guidelines
- **Tool design**: `read`, `write`, `edit`, `bash` are standard, but `apply_patch` is Claude Code-inspired
- **CLI UX**: Typer + Rich for clean terminal output

**What we changed**:
- Claude Code has UI, MCP ecosystem, git integration — we're CLI-only for simplicity

---

## What Is Intentionally Out of Scope

These are good ideas, but not implemented because they're beyond interview scope:

### Authentication & Multi-Tenancy
- No user accounts, no auth, no rate limiting
- Assumes single-user, local-only execution

### Distributed Tracing
- Events are session-local, not sent to observability platforms (Datadog, Honeycomb, etc.)

### Context Compaction
- No LLM-based summarization or token counting (tiktoken)
- Character-based approximation is "good enough" for demos

### Resume/Replay
- Trace reading works, but no `codeagent resume <session-id>` command yet
- Foundation is complete, just needs CLI hook

### MCP Ecosystem
- MCP extension exists, but no pre-built server integrations
- Users must configure MCP servers manually

### Interactive Confirmation UI
- Policy returns `confirm` verdicts, but no TUI prompt yet
- In simplified mode, confirm = allow

### Streaming Responses
- API calls are one-shot (request → response)
- No streaming tokens or incremental tool results

---

## Summary

CodeAgent-Py is designed to:
1. **Demonstrate understanding** of agent runtime architecture (provider abstraction, event stream, safety layers)
2. **Be interview-grade**: Clean, tested, honest about scope
3. **Balance simplicity and correctness**: No unnecessary complexity, but production patterns where they matter

The result is a runtime that's **testable** (120 tests), **safe** (defense in depth), **observable** (event stream), and **portable** (provider protocol).
