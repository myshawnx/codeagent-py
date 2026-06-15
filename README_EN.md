# CodeAgent-Py

[中文 README](README.md)

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-165%20passing-brightgreen.svg)](#testing)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**CodeAgent-Py is a Python-first, local-first coding-agent runtime.**

It is not a thin script that sends a prompt to a model. It separates the runtime into explicit engineering layers: model providers, agent loop, tool registry and execution, policy gateway, safety boundaries, runtime events, JSONL traces, session resume, eval harness, MCP integration, and observability sinks.

The goal is to provide a testable and inspectable local runtime where an LLM can read code, edit files, run controlled commands, record what happened, and be evaluated through deterministic offline tests.

---

## What It Does

A typical CodeAgent-Py task follows this flow:

```text
user task
  -> build project context
  -> call model provider
  -> parse text or tool calls
  -> run policy checks
  -> execute local tools inside workspace safety boundaries
  -> return tool results to the model
  -> repeat until final answer or guard limit
  -> persist runtime events as JSONL traces
```

Implemented capabilities include:

- local file read, write, edit, patch, and git diff tools
- constrained bash execution
- allow / confirm / deny policy decisions
- workspace path safety checks
- runtime event stream
- JSONL session traces and linear resume
- offline agent-loop tests through `MockProvider`
- deterministic YAML eval scenarios
- stdio MCP presets
- parallel execution for read-only tools marked as safe
- read-result caching with invalidation after writes

---

## Current Status

| Area | Status | Notes |
|---|---:|---|
| Provider abstraction | Done | Runtime depends on normalized `ModelProvider` types |
| Anthropic provider | Done | Uses the official Anthropic Python SDK |
| Mock provider | Done | Supports offline tests and deterministic evals |
| Agent loop | Done | Handles text, tool calls, tool results, and stopping conditions |
| Streaming | Done | Provider-neutral stream events and CLI `--stream` |
| Local tools | Done | `read`, `write`, `edit`, `apply_patch`, `git_diff`, `bash` |
| Policy gateway | Done | Allow / confirm / deny decisions |
| Tool safety | Done | Blocks path traversal, absolute escapes, and symlink escapes |
| Runtime events | Done | Captures model, tool, policy, session, and error events |
| JSONL traces | Done | Saves sessions under `.agent/sessions/<session_id>.jsonl` |
| Resume | Done | Reconstructs normalized messages from traces |
| Eval harness | Done | YAML scenarios, metrics, reports, and trace export |
| MCP integration | Baseline | Stdio client plus filesystem and GitHub presets |

Current expected test result:

```text
165 passed, 4 skipped
```

The skipped tests require real credentials or environment setup. The core runtime is covered by deterministic offline tests.

---

## Architecture

```text
CLI
  -> AgentSession
    -> Context Builder
    -> AgentLoop
      -> ModelProvider
        -> AnthropicProvider
        -> MockProvider
      -> Tool Registry
      -> Extension Hooks
        -> PolicyGateway
        -> LoopGuards
      -> EventBus
        -> InMemorySink
        -> ConsoleSink
        -> TraceWriter
```

Repository layout:

```text
src/codeagent/
├── providers/          ModelProvider abstraction and concrete providers
├── runtime/            AgentLoop, AgentSession, tools, events, extensions
├── policy/             Policy engine, gateway, and approval handlers
├── loop/               Budgets, repeated-failure guards, reward-hacking guard
├── context/            Project profile detection and system prompt builder
├── trace/              JSONL trace persistence and resume reconstruction
├── eval/               YAML eval harness, benchmarks, reports, metrics
├── mcp/                Stdio MCP integration and preset helpers
├── util/               Workspace path safety helpers
└── cli/                Typer CLI commands
```

---

## Quick Start

```bash
git clone https://github.com/myshawnx/codeagent-py.git
cd codeagent-py
uv sync
```

For real model calls:

```bash
export ANTHROPIC_API_KEY=your-key-here
```

Initialize config:

```bash
uv run codeagent init
```

Run tasks:

```bash
uv run codeagent ask "Explain this codebase" --mode readonly
uv run codeagent ask "Fix the bug in src/example.py" --mode workspace-write
uv run codeagent ask "Explain this codebase" --mode readonly --stream
```

Inspect or resume sessions:

```bash
uv run codeagent sessions
uv run codeagent sessions <session-id>
uv run codeagent resume <session-id> "continue from here"
```

Run evals:

```bash
uv run codeagent eval --benchmark simple_edit
uv run codeagent eval --benchmark security
uv run codeagent eval --benchmark all
```

Run tests:

```bash
uv run pytest
```

---

## Strengths

- Local-first runtime with visible tool execution and safety checks.
- Explicit provider abstraction instead of SDK-specific runtime code.
- Offline testability through `MockProvider`.
- Clear separation between policy decisions and hard tool-level safety.
- Structured runtime events and JSONL traces for debugging.
- Linear session resume from traces.
- YAML eval harness for repeatable behavior checks.
- Modular extension points for providers, tools, policy, sinks, and MCP.

---

## Limitations

- It is a runtime project, not a polished commercial coding assistant.
- It does not provide a full TUI, IDE plugin, desktop app, account system, billing, or hosted task orchestration.
- Safety is workspace-level and tool-level; it is not a container or OS-level sandbox.
- Anthropic is the main real provider today, though the provider abstraction is ready for more.
- Resume is linear; fork/tree sessions are future work.
- MCP integration is a practical baseline, not a full marketplace or lifecycle manager.
- The eval harness is best for deterministic regression tests, not broad model-quality benchmarking.

---

## Documentation

- [README.md](README.md): Chinese README
- [ARCHITECTURE.md](ARCHITECTURE.md): system architecture
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md): design rationale and tradeoffs
- [DEMO.md](DEMO.md): demo script
- [IMPROVEMENT_SUMMARY.md](IMPROVEMENT_SUMMARY.md): improvement summary
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md): project overview
- [UPDATE_SUMMARY.md](UPDATE_SUMMARY.md): update summary
- [MIGRATION.md](MIGRATION.md): migration notes

---

## License

MIT License.
