# Migration Notes: Agent CLI to CodeAgent-Py

## Purpose

CodeAgent-Py began as a Python continuation of the earlier TypeScript `agent-cli` project.

The goal was not a line-by-line port. The goal was to preserve the valuable agent-runtime ideas while making the system more natural to discuss and extend in Python:

- provider abstraction
- policy and approval control
- safe local tools
- event traces
- evals
- MCP integration
- project profile / memory primitives

## Migration Result

The Python version is now more than a direct migration. It is a hardened runtime rewrite with additional capabilities:

- provider-neutral model types
- Anthropic async adapter
- MockProvider for offline tests
- provider-level token counting
- streaming runtime
- JSONL traces
- linear resume
- approval handlers
- richer eval metrics
- MCP presets
- parallel safe tools
- read cache
- EventSink observability abstraction

Current expected test result:

```text
165 passed, 4 skipped
```

## Feature Mapping

| Capability | TypeScript agent-cli | CodeAgent-Py |
|---|---:|---:|
| Agent loop | Pi/framework-oriented | Custom Python `AgentLoop` |
| Provider abstraction | Product-oriented | Explicit `ModelProvider` |
| Mock/offline testing | Partial | First-class `MockProvider` |
| Local tools | Yes | Hardened and expanded |
| Policy engine | Yes | Pure-function classifier |
| Approval modes | Yes | Policy + approval handlers |
| Tool safety | Yes | Workspace resolver plus tool hardening |
| Loop guards | Yes | Token, tool-call, repeated failure, reward-hacking guards |
| Event traces | Yes | JSONL EventBus traces |
| Resume | Partial/history-oriented | Linear resume from JSONL |
| Eval harness | Yes | YAML scenarios, metrics, reports, traces |
| MCP | Yes | stdio client, extension, filesystem/GitHub presets |
| Streaming | Not the original focus | Provider-neutral streaming |
| Parallel tools | Not central | Safe read-only parallel execution |
| Tool cache | Not central | read cache with invalidation |
| Observability sinks | Not central | EventSink protocol |

## What Changed Architecturally

### Runtime Ownership

The Python version owns the loop directly:

```text
AgentSession -> AgentLoop -> ModelProvider -> Tools -> Events
```

This makes the runtime easier to inspect and test in interviews.

### Provider Boundary

The runtime no longer consumes vendor SDK objects directly. Provider adapters translate SDK responses into normalized model types.

### Safety Model

Safety is layered:

1. policy classify
2. approval handler
3. loop guards
4. workspace path resolver
5. tool-level limits
6. event trace accountability

### Eval-First Design

The eval harness is now a first-class package under `src/codeagent/eval/`.

Built-in benchmarks cover:

- simple edits
- security attempts
- multi-file refactor
- test-driven fix
- instruction following

## Known Differences

CodeAgent-Py intentionally does not try to recreate every product-level feature from the TypeScript project or from commercial tools.

Still future work:

- fork/tree session graph
- SDK/RPC parity
- polished TUI / IDE integration
- hosted sandboxing
- full MCP marketplace lifecycle
- multi-agent orchestration

## Current Recommendation

Use the Python version as the main interview artifact.

Use the TypeScript version as historical context for lineage and design continuity.

Best description:

> CodeAgent-Py is the Python-first hardening pass of the earlier Agent CLI ideas, with stronger provider abstraction, testing, observability, evals, resume, MCP presets, safe parallel tools, and caching.
