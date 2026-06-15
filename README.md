# CodeAgent-Py

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-157%20passing-brightgreen.svg)](#testing)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**CodeAgent-Py is a Python-first local coding-agent runtime built as an interview-grade systems project.**

It is inspired by **Claude Code**, **OpenAI Codex-style coding agents**, and **Pi Agent**, but it is intentionally smaller: the goal is not to clone a commercial coding assistant. The goal is to demonstrate that the author understands the core infrastructure behind production coding agents:

- model-provider abstraction
- tool calling and tool-result normalization
- async model execution
- policy and approval modes
- tool-level filesystem safety
- runtime event streams
- JSONL session traces
- project context building
- deterministic evals
- testable offline agent loops

If you are reviewing this project for an AI Agent / Coding Agent role, start with the architecture and tests rather than the CLI polish.

---

## Project Positioning

### What this project is

CodeAgent-Py is a **local agent runtime** that runs in a developer workspace, calls Claude through the Anthropic SDK, executes local tools, applies policy checks, and records the session as structured events.

It is meant to answer interview questions such as:

- How do you build a safe tool-calling loop?
- How do you decouple an agent runtime from one model provider?
- How do you test an agent without spending API credits?
- How do you record enough data to debug an agent trace?
- How do you separate policy decisions from tool-level safety?
- How do you keep the design understandable instead of hiding it behind a framework?

### What this project is not

CodeAgent-Py is **not** a production competitor to Claude Code, Codex, Cursor, or other commercial coding agents.

It currently does not aim to provide:

- a polished TUI / IDE / desktop experience
- hosted cloud sandboxes
- background long-running task orchestration
- polished real-time streaming UI beyond the current CLI stream output
- full TUI / IDE-grade permission prompts
- full MCP server marketplace integration
- multi-agent orchestration
- production auth, billing, telemetry, or rate limiting

Those are product and platform layers. This repository focuses on the runtime foundation.

---

## Lineage: Pi Agent → Agent CLI → CodeAgent-Py

This repository is best understood as the **Python continuation of the earlier TypeScript `agent-cli` project**, which itself adapted ideas from Pi Agent and added practical CLI-facing coding-agent features.

So the comparison is not only:

```text
CodeAgent-Py vs Claude Code / Codex / Pi Agent
```

It is also:

```text
Pi Agent as a library
  -> Agent CLI as a TypeScript coding-agent CLI
    -> CodeAgent-Py as a Python-first rewrite and hardening pass
```

The goal for CodeAgent-Py is to preserve the important Agent CLI ideas while making the implementation easier to discuss in Python AI-infrastructure interviews.

### Feature Parity Map

| Capability | Pi Agent as a library | Agent CLI net addition | CodeAgent-Py status |
|---|---:|---|---|
| Agent loop, tool calling, state | ✅ Native | Reused | ✅ Implemented as a custom Python `AgentLoop` |
| Read / write / edit / bash tools | ✅ Native | Reused and hardened through policy gateway | ✅ Implemented; additionally adds `apply_patch` and `git_diff` |
| Session persistence / resume / fork | ✅ Native tree-shaped JSONL | Reused; `TaskView` projected from it | ✅ JSONL traces and linear resume implemented; fork/tree is future work |
| `-p` print mode / SDK / RPC | ✅ Native | Thin CLI wrapper | ⚠️ CLI has `--print` flag, but SDK/RPC parity is not complete |
| Declarative approval modes + command risk tiers | ❌ | ★ Net new in Agent CLI | ✅ Implemented via pure-function policy engine, `PolicyGateway`, and approval handlers |
| MCP integration over stdio JSON-RPC | ❌ | ★ Net new in Agent CLI | ⚠️ Stdio MCP extension plus filesystem/GitHub presets; not yet a marketplace |
| Eval / benchmark framework | ❌ | ★★ Strongest hiring signal in Agent CLI | ✅ YAML eval harness with richer scenarios, metrics, and trace export; model matrices remain future work |
| Project profile + cross-session memory | ❌ | ★ Small but realistic addition | ⚠️ Project profile implemented; memory primitives exist; deeper memory use is future work |

### Honest Parity Assessment

CodeAgent-Py currently preserves the **architectural intent** of Agent CLI, but it is not yet a one-to-one feature clone.

The strongest parity areas are:

- agent loop and tool calling
- policy engine and approval modes
- command risk classification
- project profile detection
- eval harness
- local tool safety
- trace persistence foundation

The biggest remaining parity gaps are:

- tree/fork session model
- SDK/RPC surface
- richer TUI / IDE confirmation flows
- full MCP marketplace / server lifecycle
- deeper cross-session memory integration

This is intentional for the current interview scope: the Python version prioritizes **runtime clarity, safety hardening, provider abstraction, and tests** before rebuilding every product-level feature from Agent CLI.

---

## Feature Overview

| Area | Implemented | Why it matters |
|---|---:|---|
| Provider abstraction | ✅ | Runtime depends on normalized `ModelProvider`, not Anthropic SDK objects |
| Anthropic provider | ✅ | Uses the official Anthropic Python SDK through an async adapter |
| Mock provider | ✅ | Enables offline tests for full tool-use loops |
| Provider token counting | ✅ | Anthropic uses official `messages.count_tokens`; fallback counts are marked estimated |
| Streaming responses | ✅ | Provider-neutral stream events, runtime events, and CLI `--stream` output |
| Tool calling | ✅ | Normalized `tool_use` and `tool_result` blocks |
| Runtime events | ✅ | Emits structured events for debugging, evals, and traces |
| JSONL traces | ✅ | Saves sessions under `.agent/sessions/<session_id>.jsonl` |
| Policy engine | ✅ | Pure-function classify layer for allow / confirm / deny decisions |
| Approval modes | ✅ | `readonly`, `suggest`, `workspace-write`, `auto` |
| Approval handlers | ✅ | Rich CLI prompt, auto approval, non-interactive deny, and recording handler |
| Tool-level safety | ✅ | Blocks path traversal, absolute escapes, and symlink escapes |
| Bash hardening | ✅ | Timeout, output truncation, exit status handling |
| File tools | ✅ | `read`, `write`, `edit`, `apply_patch`, `git_diff` |
| Loop guards | ✅ | Tool-call limit, token budget, repeated failure guard, reward-hacking guard |
| Context builder | ✅ | Loads project instructions and detected project profile; supports provider-backed token budgets |
| Eval harness | ✅ | YAML scenarios, structured metrics, eval traces, and markdown / JSON reports |
| MCP integration | ⚠️ | Stdio extension, `.agent/mcp.json`, filesystem/GitHub presets, and env-based credentials |
| Resume | ✅ | Linear resume reconstructs normalized messages from JSONL traces |
| Streaming UI | ✅ | CLI `--stream` is implemented; richer TUI/IDE streaming remains future work |

---

## Why This Project Is Interesting

Most small coding-agent demos put everything in one loop:

```text
prompt -> model -> maybe call a tool -> print result
```

CodeAgent-Py instead separates the runtime into explicit layers:

```text
CLI
  -> AgentSession
    -> Context Builder
    -> AgentLoop
      -> ModelProvider
        -> AnthropicProvider / MockProvider
      -> Tool Registry
      -> Extension Hooks
        -> PolicyGateway
        -> LoopGuards
      -> EventBus
        -> JSONL TraceWriter
```

This makes the project useful for interviews because each layer can be discussed, tested, and extended independently.

---

## Comparison with Claude Code, Codex, and Pi Agent

This project borrows ideas from several agent systems, but makes different tradeoffs.

### High-Level Comparison

| Dimension | Claude Code | OpenAI Codex-style Agents | Pi Agent | CodeAgent-Py |
|---|---|---|---|---|
| Primary goal | Production coding assistant | Model / agent product for coding tasks | Research / framework-style agent patterns | Interview-grade local runtime |
| UX polish | Very high | Product-dependent | Low to medium | Low; CLI-first |
| Local runtime clarity | Hidden behind product | Hidden or provider-specific | Good | Very high |
| Provider abstraction | Claude-focused | OpenAI-focused | Varies | Explicit `ModelProvider` protocol |
| Offline testing | Not the main focus | Not the main focus | Partial | First-class via `MockProvider` |
| Tool safety | Product-managed | Product / sandbox-managed | Framework-dependent | Explicit policy + tool safety layers |
| Event trace model | Product-internal | Product-internal | Trajectory-oriented | Public JSONL event stream |
| Evals | Product-internal | Product-internal | Research-oriented | YAML deterministic evals |
| Extensibility | Through product hooks / MCP | Through platform APIs | Framework extension | Python modules and extension hooks |
| Best use case | Daily professional coding | Hosted coding assistance / model-driven coding | Agent research patterns | Showing agent infrastructure knowledge |

---

## Claude Code vs CodeAgent-Py

**Claude Code** is Anthropic's production coding assistant available through the CLI, IDE integrations, desktop, and web surfaces. It has a much richer user experience, mature product workflows, and deep integration with Claude models.

CodeAgent-Py is much smaller, but it exposes the internals that are useful in an interview.

### Where Claude Code is stronger

- polished interactive UX
- high-quality coding behavior backed by Claude models
- mature CLI / IDE / desktop workflows
- built-in product-level context handling
- better real-world ergonomics for daily development
- broader ecosystem integration, including MCP-style workflows

### Where CodeAgent-Py is stronger as an interview artifact

- the runtime code is small enough to read in one sitting
- provider abstraction is explicit and testable
- full agent loop can be tested offline with `MockProvider`
- event stream is visible and persisted as JSONL
- policy logic is pure-function and unit-tested
- tool safety is implemented in local Python code, not hidden behind a product boundary

### Honest takeaway

Use Claude Code for real work. Use CodeAgent-Py to show that you understand how a Claude-Code-like runtime could be built.

---

## Codex-Style Agents vs CodeAgent-Py

The term **Codex** is used here broadly to refer to OpenAI-style coding agents and coding-model workflows. Codex-style systems are usually strongest when the platform provides a capable model, hosted execution environment, or polished product loop.

CodeAgent-Py takes a different angle: it focuses on the local harness around the model.

### Where Codex-style systems are stronger

- stronger product integration when used through the vendor's native environment
- potentially better hosted sandboxing depending on the platform
- model-native coding workflows and benchmark-tuned behavior
- less infrastructure to build yourself

### Where CodeAgent-Py is stronger as a learning project

- provider-neutral internal request / response types
- explicit tool schemas and execution boundaries
- local workspace safety checks you can inspect
- transparent event history
- deterministic YAML eval harness
- no dependency on a hosted agent platform for tests

### Honest takeaway

Codex-style agents are closer to a product or platform surface. CodeAgent-Py is closer to a reference runtime for understanding how coding-agent infrastructure works.

---

## Pi Agent vs CodeAgent-Py

**Pi Agent** influenced this project most at the architecture level: agent trajectories, explicit policy decisions, small composable components, and eval-oriented thinking.

CodeAgent-Py adapts those ideas into a Python-first local coding assistant.

### What CodeAgent-Py borrows from Pi Agent

- trajectory-style thinking through event traces
- policy as a separable decision layer
- eval-first mindset
- explicit tool calls and tool results
- a preference for small, testable units over framework magic

### Where Pi Agent is stronger

- more research-oriented agent abstractions
- deeper trajectory concepts
- better conceptual foundation for branching and replay patterns
- closer to an experimental agent framework

### Where CodeAgent-Py is stronger for coding-agent interviews

- concrete local coding tools
- workspace filesystem safety
- approval modes similar to coding-agent products
- Typer/Rich CLI
- Python package structure that resembles production app code
- focused tests around coding-agent failure modes

### Honest takeaway

Pi Agent is a source of architectural inspiration. CodeAgent-Py is a practical adaptation for local coding-agent runtime interviews.

---

## Core Architecture

### Provider Layer

The runtime does not depend directly on Anthropic SDK response objects.

```python
class ModelProvider(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        ...

    async def count_tokens(self, request: ModelRequest) -> TokenCount:
        ...

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        ...
```

Implemented providers:

- `AnthropicProvider` — real model calls through the official Anthropic Python SDK
- `MockProvider` — scripted responses for offline tests and deterministic evals

Normalized internal types include:

- `ModelRequest`
- `ModelResponse`
- `ModelStreamEvent`
- `TokenCount`
- `ModelMessage`
- `TextBlock`
- `ToolUseBlock`
- `ToolResultBlock`
- `Usage`

This is the main seam that makes the runtime portable.

---

### Agent Loop

The loop is intentionally explicit:

1. append user message
2. build normalized model request
3. call provider
4. append assistant response
5. if `tool_use`, run policy and tool execution
6. append tool results
7. repeat until final answer or turn limit

This is implemented in `src/codeagent/runtime/loop.py`.

---

### Runtime Event Stream

Every meaningful step emits an event:

- `session_start`
- `turn_start`
- `model_request`
- `model_stream_start`
- `model_text_delta`
- `model_stream_end`
- `model_response`
- `tool_call_requested`
- `policy_verdict`
- `tool_start`
- `tool_end`
- `turn_end`
- `session_end`
- `error`

Events are collected in memory and can be persisted as JSONL.

Example trace line:

```json
{
  "id": "evt_...",
  "timestamp": 1760000000.0,
  "type": "tool_end",
  "session_id": "...",
  "parent_id": "...",
  "payload": {
    "tool": "read",
    "is_error": false
  }
}
```

---

### Policy and Safety Layers

CodeAgent-Py deliberately separates **policy decisions** from **tool-level enforcement**.

#### Policy layer

The policy engine decides whether a tool call should be allowed, confirmed, or denied.

```python
verdict = classify(event, mode, policy, opts)
```

This layer is pure-function and easy to test.

#### Tool layer

The tool layer enforces hard boundaries regardless of policy configuration.

```python
resolve_in_workspace(root, user_path)
```

It prevents:

- `../` path traversal
- absolute path escape
- symlink escape
- large file reads / writes
- ambiguous edits
- runaway bash commands

This is defense in depth: even if policy is misconfigured, tools still protect the workspace boundary.

---

## Built-In Tools

| Tool | Purpose | Safety behavior |
|---|---|---|
| `read` | Read a file | Workspace-bound, size-limited |
| `write` | Write a file | Workspace-bound, size-limited |
| `edit` | Replace unique text | Rejects ambiguous matches |
| `apply_patch` | Apply unified diff | Workspace-bound patch application |
| `git_diff` | Inspect working diff | Read-only |
| `bash` | Execute shell command | Timeout, stdout/stderr truncation |

The tools are intentionally simple. They are meant to demonstrate safety boundaries, not replace a full sandbox.

---

## Context Builder

The context builder assembles a useful system prompt from project-local information.

Instruction precedence:

```text
.agent/instructions.md
  > AGENTS.md
  > CLAUDE.md
```

Detected project profile may include:

- language
- package manager
- framework
- test framework
- likely test / lint commands

Example:

```text
Language: python
Package manager: uv
Test framework: pytest
Test command: pytest
Lint command: ruff check
```

The current implementation exposes provider-level token counting through `ModelProvider.count_tokens()`. Anthropic uses the official `messages.count_tokens` API, MockProvider supports deterministic counts for tests, and fallback estimates are explicitly marked as estimated. The context builder can use these provider-backed counts when trimming project instructions.

---

## Evaluation Harness

CodeAgent-Py includes a deterministic YAML-based eval harness.

```bash
uv run codeagent eval --benchmark simple_edit
uv run codeagent eval --benchmark security
uv run codeagent eval --benchmark test_driven_fix
uv run codeagent eval --scenario-file path/to/scenario.yaml
```

Built-in benchmark groups:

- `simple_edit` — basic code-editing tasks
- `security` — path escape, `.env` write, symlink escape, dangerous command, reward-hacking attempt
- `multi_file_refactor` — duplicated logic extraction across multiple files
- `test_driven_fix` — failing-test repair while protecting tests from reward hacking
- `instructions` — AGENTS.md instruction-following scenarios

Eval reports include structured metrics for tool calls, token usage, expected files changed, forbidden files touched, post-run tests, and dangerous operation blocking. CLI eval runs save per-scenario JSONL traces under `.agent/eval-traces/<scenario>.jsonl` by default; use `--no-save-traces` to disable trace export.

The eval harness is intentionally lightweight. Its purpose is to show how a coding agent can be regression-tested without depending only on manual demos.

---

## Quick Start

### Requirements

- Python 3.11+
- `uv`
- Anthropic API key for real model calls

### Install

```bash
git clone https://github.com/myshawnx/codeagent-py.git
cd codeagent-py
uv sync
```

### Configure API key

```bash
export ANTHROPIC_API_KEY=your-key-here
```

### Initialize project config

```bash
uv run codeagent init
```

### Run a task

```bash
uv run codeagent ask "Explain this codebase" --mode readonly
uv run codeagent ask "Fix the bug in src/example.py" --mode workspace-write
uv run codeagent ask "Explain this codebase" --mode readonly --stream
```

### Inspect session traces

```bash
uv run codeagent sessions
uv run codeagent sessions <session-id>
uv run codeagent resume <session-id> "continue from here"
```

### Run tests

```bash
uv run pytest tests/ -q
```

Current expected result:

```text
157 passed, 4 skipped
```

The skipped tests require a real API key and are intentionally not part of the offline suite.

---

## CLI Commands

| Command | Purpose |
|---|---|
| `codeagent init` | Create `.agent/` config files |
| `codeagent ask "..."` | Run an agent task |
| `codeagent ask "..." --stream` | Stream model text deltas as they arrive |
| `codeagent ask --mode readonly` | Explore without writes |
| `codeagent eval --benchmark simple_edit` | Run built-in evals |
| `codeagent eval --benchmark security` | Run security scenarios |
| `codeagent eval --benchmark all --no-save-traces` | Run all benchmarks without exporting eval traces |
| `codeagent sessions` | List saved JSONL traces |
| `codeagent sessions <id>` | Inspect one trace |
| `codeagent resume <id> "..."` | Reconstruct messages from a trace and continue |
| `codeagent mcp list` | List configured MCP servers |
| `codeagent mcp presets` | Show built-in MCP presets |
| `codeagent mcp add filesystem` | Add the filesystem MCP preset |
| `codeagent mcp add github` | Add the GitHub MCP preset using environment credentials |

---

## Testing

Run the full suite:

```bash
uv run pytest tests/ -q
```

Important test groups:

```bash
uv run pytest tests/unit/test_providers.py -q
uv run pytest tests/unit/test_events.py -q
uv run pytest tests/unit/test_tool_safety.py -q
uv run pytest tests/unit/test_trace.py -q
uv run pytest tests/unit/test_context.py -q
uv run pytest tests/unit/test_policy.py -q
uv run pytest tests/unit/test_eval.py -q
```

What the tests prove:

- provider normalization works
- provider token counting and fallback behavior work
- provider-neutral streaming and runtime stream events work
- the agent loop can run offline through `MockProvider`
- tool calls and tool results round-trip correctly
- policy verdicts are emitted as events
- approval requests and approval decisions are emitted as events
- path traversal and symlink escape are blocked
- bash timeout behavior is covered
- JSONL traces can be written and read back
- JSONL traces can reconstruct messages for linear resume
- eval scenarios load richer benchmarks and collect structured metrics
- project instruction precedence works

---

## Repository Layout

```text
src/codeagent/
├── providers/          # ModelProvider abstraction and concrete providers
├── runtime/            # AgentLoop, AgentSession, tools, events, extensions
├── policy/             # Pure-function policy engine and gateway extension
├── loop/               # Loop guards: budgets, repeated failures, reward hacking
├── context/            # Project profile detection and system prompt builder
├── trace/              # JSONL event trace persistence
├── eval/               # YAML eval harness and benchmarks
├── mcp/                # Stdio MCP integration and preset config helpers
├── util/               # Workspace path safety helpers
└── cli/                # Typer CLI commands
```

---

## Design Tradeoffs

### Why not LangChain?

Because the goal is to demonstrate the underlying runtime mechanics. A framework would hide the most important interview topics: the loop, provider normalization, tool execution, policy gates, and trace design.

### Why Python?

Python is common in AI infrastructure, easy to test, and has a strong CLI / typing / validation ecosystem through Typer, Rich, and Pydantic.

### Why local tools instead of a hosted sandbox?

A hosted sandbox is better for production isolation, but a local tool runtime makes the safety boundaries visible and testable. This is useful for an interview project.

### Why JSONL traces?

JSONL is simple, append-friendly, diffable, and easy to inspect. Current traces include enough normalized model request / response payload to reconstruct conversation messages for linear resume; fork/tree sessions remain future work.

### Why keep the project small?

Because this is not a product clone. The code should be understandable in a code review and extensible in a live interview.

---

## Known Limitations

| Limitation | Current state | Better future version |
|---|---|---|
| Streaming UX | Provider-neutral streaming and CLI `--stream` implemented | Richer TUI/IDE progress, richer tool-use deltas |
| Resume model | Linear resume implemented from JSONL traces | Fork/tree sessions and external process replay |
| Token counting | Provider-level counting implemented for Anthropic and Mock; fallback estimates are marked | More providers and deeper budget integration across full conversation history |
| Confirmation UI | `confirm` verdicts route through approval handlers; local CLI uses Rich prompts, print mode denies non-interactively, and auto mode auto-approves | Richer TUI / IDE approval prompt |
| MCP ecosystem | Filesystem/GitHub presets configure stdio servers with env-based credential placeholders | Broader curated presets, server health checks, and richer credential UX |
| Sandboxing | Workspace safety only | Container / OS-level sandbox |
| Multi-agent | Not implemented | Subagent orchestration with scoped traces |
| Production telemetry | JSONL local traces | OpenTelemetry / metrics backend |

These limitations are intentional scope boundaries, not hidden product claims.

---

## Recommended Interview Walkthrough

A strong 5-minute demo:

1. **Show provider abstraction**
   - `providers/types.py`
   - `providers/anthropic_provider.py`
   - `providers/mock_provider.py`

2. **Run offline tests**
   ```bash
   uv run pytest tests/unit/test_events.py -q
   ```

3. **Show tool safety**
   - `util/workspace.py`
   - `tests/unit/test_tool_safety.py`

4. **Show event tracing**
   - `runtime/events.py`
   - `trace/writer.py`
   - `.agent/sessions/*.jsonl`

5. **Show policy separation**
   - `policy/engine.py`
   - `policy/gateway.py`

6. **Run evals**
   ```bash
   uv run codeagent eval --benchmark security
   ```

---

## Suggested Next Improvements

If continuing this project, the highest-value improvements are:

1. **Fork/tree resume**
   - branch from existing traces
   - preserve parent/child session relationships

2. **Sandboxing**
   - run tools in containers
   - isolate network access
   - capture filesystem diffs

3. **Parallel safe tools**
   - run read-only tool calls concurrently
   - keep mutating tools serialized

4. **MCP hardening**
   - server health checks
   - richer preset validation

---

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — deeper system design
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) — rationale and tradeoffs
- [DEMO.md](DEMO.md) — interview demo script
- [IMPROVEMENT_SUMMARY.md](IMPROVEMENT_SUMMARY.md) — implementation summary

---

## License

MIT License.

---

## Final Note

CodeAgent-Py is intentionally modest in product scope but serious in architecture. It is designed to make the important parts of coding-agent infrastructure visible: model abstraction, tool execution, policy gates, safety boundaries, event traces, and evals.

That is the point of the project: not to out-feature Claude Code or Codex, but to show that the foundations of such systems are understood and implemented cleanly.
