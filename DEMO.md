# CodeAgent-Py Demo Guide

This guide provides a 5-minute walkthrough for demonstrating CodeAgent-Py's capabilities and architecture.

---

## Setup (30 seconds)

```bash
# Clone and install
git clone https://github.com/yourusername/codeagent-py.git
cd codeagent-py
uv sync

# Set API key
export ANTHROPIC_API_KEY=your-key-here

# Initialize project
uv run codeagent init
```

**Output**: Creates `.agent/` directory with policy, profile, and memory.

---

## Demo 1: Safe Read Operation (1 minute)

**Goal**: Show the agent can explore code safely.

```bash
# Create a test file
echo "def hello():\n    return 'world'" > test.py

# Ask agent to read it
uv run codeagent ask "What does test.py do?" --mode readonly
```

**Expected outcome**:
- Agent reads the file successfully
- Explains it's a simple function
- **Trace saved**: Check `.agent/sessions/<id>.jsonl`

**Key point**: Readonly mode only allows read operations.

```bash
# List sessions
uv run codeagent sessions
```

**Show**: Session ID, event count, timestamp.

---

## Demo 2: Policy Blocks Dangerous Operations (1 minute)

**Goal**: Show defense-in-depth safety.

```bash
# Try to make agent write to .env (should fail)
uv run codeagent ask "Create a .env file with API_KEY=secret"
```

**Expected outcome**:
- Agent attempts to write
- Policy blocks the operation: "Protected path: .env"
- Trace shows `policy_verdict: deny`

**Key point**: Safety enforced at BOTH policy layer AND tool layer.

**Prove tool-level safety**:
```bash
# Run the path traversal test
uv run pytest tests/unit/test_tool_safety.py::TestWorkspacePathSafety::test_deny_parent_escape -v
```

**Show**: Even without policy, tools prevent `../` escape.

---

## Demo 3: Offline Testing with MockProvider (1 minute)

**Goal**: Show testability without API key.

```bash
# Run offline agent loop tests (no API calls)
uv run pytest tests/unit/test_events.py::TestOfflineAgentLoop -v
```

**Expected outcome**:
- Tests pass without `ANTHROPIC_API_KEY`
- Full tool-calling flow exercised
- Policy integration tested

**Key point**: `MockProvider` lets us test the entire runtime offline.

**Show the code**:
```bash
# Open the test file
cat tests/unit/test_events.py | grep -A 10 "def test_tool_call_flow"
```

**Highlight**: `MockProvider(responses=[...])` scripts model behavior.

---

## Demo 4: Session Trace Inspection (1 minute)

**Goal**: Show observability via event stream.

```bash
# Pick a recent session
SESSION_ID=$(uv run codeagent sessions | tail -n 1 | awk '{print $1}')

# Inspect it
uv run codeagent sessions $SESSION_ID
```

**Expected outcome**:
- Shows all events: session_start, turn_start, model_request, tool_call_requested, policy_verdict, tool_start, tool_end, turn_end, session_end
- Timestamps, payloads visible

**Key point**: Every session is automatically traced. Foundation for debugging, evals, replay.

**Show the JSONL**:
```bash
cat .agent/sessions/*.jsonl | head -5 | jq .
```

**Highlight**: Structured JSON events, one per line.

---

## Demo 5: Provider Abstraction (1 minute)

**Goal**: Show decoupling from Anthropic SDK.

**Show the architecture**:
```bash
# Open the provider abstraction
cat src/codeagent/providers/types.py | grep -A 5 "class ModelRequest"
cat src/codeagent/providers/base.py | grep -A 5 "class ModelProvider"
```

**Explain**:
- Runtime depends on `ModelProvider` protocol, not Anthropic SDK
- `AnthropicProvider` is one adapter
- `MockProvider` is another
- Adding OpenAI/Google = 1 new adapter file

**Show the normalization**:
```bash
# Open the normalization logic
cat src/codeagent/providers/anthropic_provider.py | grep -A 15 "_normalize"
```

**Highlight**: Translates SDK response objects → normalized `ModelResponse`.

---

## Architecture Overview (30 seconds)

**Whiteboard or slide**:

```
┌─────────────────────────────────────────┐
│   CLI (Typer + Rich)                   │
│   ask / init / sessions / eval         │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│   AgentSession                          │
│   - Loads context (AGENTS.md)          │
│   - Registers tools                     │
│   - Attaches trace writer               │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│   AgentLoop                             │
│   - Calls ModelProvider                 │
│   - Emits events to EventBus           │
│   - Executes tools                      │
└─────────────────────────────────────────┘
         ↓                  ↓
┌─────────────────┐  ┌─────────────────┐
│ ModelProvider   │  │ EventBus        │
│ (abstraction)   │  │ → TraceWriter   │
│                 │  │   → JSONL       │
│ - Anthropic     │  └─────────────────┘
│ - Mock          │
└─────────────────┘
         ↓
┌─────────────────────────────────────────┐
│   Tools (workspace-safe)                │
│   - resolve_in_workspace()              │
│   - read / write / edit / patch / diff  │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│   PolicyGateway (second safety layer)   │
│   - Glob-based deny/confirm rules       │
└─────────────────────────────────────────┘
```

---

## Test Coverage Walkthrough (30 seconds)

```bash
# Run full test suite
uv run pytest tests/ -v --tb=short
```

**Expected**: 120 passing, 4 skipped.

**Breakdown**:
- **P0 (24 tests)**: Provider normalization, event bus, offline loop
- **P1 (16 tests)**: Path safety, symlink escape, tool hardening
- **P2 (6 tests)**: Trace persistence, JSONL round-trip
- **P3 (17 tests)**: Context builder, instruction loading
- **Existing (57 tests)**: Policy, config, profile, loop guards

**Key point**: All new features are regression-tested.

---

## Interview Talking Points

### 1. Provider Abstraction
**Question**: "How do you decouple from vendor SDKs?"

**Answer**: 
- "We define a `ModelProvider` protocol with one method: `async def generate(request) -> response`."
- "The runtime never sees Anthropic SDK objects — only normalized types."
- "This lets us swap providers and test offline with MockProvider."

**Demo**: Show `test_tool_call_flow` test running without API key.

---

### 2. Event Stream
**Question**: "How do you debug agent behavior?"

**Answer**:
- "Every session emits structured events to an EventBus."
- "Events are auto-saved to JSONL files."
- "This powers tracing, debugging, and eval trace export."

**Demo**: `codeagent sessions` → inspect a session's events.

---

### 3. Defense in Depth
**Question**: "How do you prevent malicious tool calls?"

**Answer**:
- "Two layers: policy (user-configurable globs) and tools (hard boundaries)."
- "Even if policy has a bug, `resolve_in_workspace()` blocks escapes."
- "All file tools call this resolver before any I/O."

**Demo**: Run `test_deny_symlink_escape` test.

---

### 4. Testability
**Question**: "How do you test without burning API credits?"

**Answer**:
- "MockProvider scripts model responses — no network calls."
- "40+ tests exercise the full loop offline."
- "Policy, safety, and event emission are all testable."

**Demo**: `pytest tests/unit/test_events.py` → all pass, no API key.

---

### 5. Production Patterns
**Question**: "What makes this production-ready?"

**Answer**:
- "Async correctness: no blocking calls in async functions."
- "Timeouts: API calls and bash commands have enforced limits."
- "Structured errors: tools return clear error messages."
- "Observability: event stream is the single source of truth."

**Demo**: Show `AnthropicProvider` timeout handling.

---

## Honest Limitations

**What this is NOT**:
- Not a full Claude Code clone (no UI, no git integration, no MCP ecosystem)
- Not production-deployed (no auth, rate limiting, telemetry)
- Not feature-complete (context compaction, resume command are future work)

**Why it's interview-grade**:
- Clean architecture (provider, events, safety)
- Well-tested (120 tests, 98% coverage)
- Honest about scope (documented trade-offs)

---

## Next Steps After Demo

If the interviewer wants to go deeper:

### Code Review
- **Best file to read**: `src/codeagent/runtime/loop.py` — shows provider integration, event emission, tool execution
- **Best test to read**: `tests/unit/test_events.py::test_tool_call_flow` — shows full offline loop

### Architecture Discussion
- **DESIGN_DECISIONS.md**: Explains "why not LangChain", "why Python", etc.
- **IMPROVEMENT_SUMMARY.md**: Before/after comparison, metrics, trade-offs

### Live Coding Challenge
- "Add a new provider (e.g., OpenAI)"
- "Add a new tool (e.g., `grep`)"
- "Add a new event type"

All of these are ~10-20 lines due to the clean abstractions.

---

## Closing Points

1. **Scope control**: Delivered P0-P3 cleanly instead of half-implementing P0-P5.
2. **Engineering judgment**: Fixed latent bugs, added safety, maintained backward compat.
3. **Testability**: MockProvider shows understanding of seams and dependency injection.
4. **Documentation**: Honest about what's done and what's future work.

**Final message**: "This project demonstrates production-grade agent runtime architecture without over-engineering. The foundation is solid, tested, and ready to build on."

---

## Quick Reference

### Commands
```bash
uv run codeagent init                    # Initialize project
uv run codeagent ask "..." [--mode M]    # Run agent
uv run codeagent sessions                # List sessions
uv run codeagent sessions <id>           # Inspect session
uv run pytest tests/ -v                  # Run all tests
```

### Key Files
- `src/codeagent/providers/` — Provider abstraction
- `src/codeagent/runtime/loop.py` — Agent loop
- `src/codeagent/util/workspace.py` — Path safety
- `src/codeagent/trace/writer.py` — Session persistence
- `DESIGN_DECISIONS.md` — Architecture rationale
- `IMPROVEMENT_SUMMARY.md` — Before/after metrics

### Test Highlights
- `tests/unit/test_events.py::test_policy_blocks_tool` — Offline policy test
- `tests/unit/test_tool_safety.py::test_deny_symlink_escape` — Safety test
- `tests/unit/test_providers.py::test_normalize_text_and_tool_use` — Provider normalization
- `tests/unit/test_context.py::test_session_loads_instructions` — Context integration
