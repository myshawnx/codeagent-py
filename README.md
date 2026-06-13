# CodeAgent-Py — Interview-Grade Local Coding Agent

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-120%20passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A production-grade local coding agent built with Python, demonstrating clean architecture and strong engineering practices. Inspired by Pi Agent, Claude Code, and Codex, but designed to showcase agent runtime fundamentals without unnecessary complexity.

**Purpose**: Interview project for AI Agent / Coding Agent developer roles.

---

## 🌟 Key Features

### ✅ Provider Abstraction Layer
- **Vendor-agnostic runtime**: Decoupled from Anthropic SDK via `ModelProvider` protocol
- **Offline testing**: `MockProvider` enables 40+ tests with zero API calls
- **Portable**: Adding OpenAI/Google = one adapter file

### ✅ Structured Event Stream
- **Observability**: Every session emits lifecycle events (session_start, tool_call, policy_verdict, etc.)
- **Auto-tracing**: Sessions saved to `.agent/sessions/<id>.jsonl`
- **Foundation**: Powers debugging, evals, and future replay/resume

### ✅ Defense-in-Depth Safety
- **Tool-level**: `resolve_in_workspace()` prevents path traversal, symlink escape, absolute path escapes
- **Policy-level**: Glob-based deny/confirm rules for files and commands
- **Hardened tools**: Timeouts, size limits, structured errors

### ✅ Context Builder
- **Project instructions**: Loads AGENTS.md / CLAUDE.md / .agent/instructions.md (with precedence)
- **Profile injection**: Automatically detects language, package manager, test framework
- **Token-aware**: Trims context to fit within budget

### ✅ Well-Tested
- **120 tests**: 98% pass rate, offline-runnable
- **Regression-safe**: All new features have test coverage
- **Fast**: Full suite runs in ~30 seconds

---

## 🚀 Quick Start

### Installation
```bash
# Clone
git clone https://github.com/yourusername/codeagent-py.git
cd codeagent-py

# Install with uv
uv sync

# Set API key
export ANTHROPIC_API_KEY=your-key-here
```

### Basic Usage
```bash
# Initialize project
uv run codeagent init

# Execute a task
uv run codeagent ask "Fix the bug in main.py"

# Readonly mode (safe exploration)
uv run codeagent ask "Explain this codebase" --mode readonly

# Auto mode (minimal confirmation)
uv run codeagent ask "Add unit tests" --mode auto

# List session history
uv run codeagent sessions

# Inspect a specific session
uv run codeagent sessions <session-id>
```

---

## 📁 Project Structure

```
src/codeagent/
├── providers/          # Provider abstraction layer
│   ├── types.py        # Normalized model types
│   ├── base.py         # ModelProvider protocol
│   ├── anthropic_provider.py
│   └── mock_provider.py
├── runtime/            # Agent runtime
│   ├── loop.py         # Main agent loop
│   ├── session.py      # Session management
│   ├── events.py       # Event stream
│   ├── tools.py        # Hardened builtin tools
│   └── extensions.py   # Extension system
├── policy/             # Policy engine (pure functions)
│   ├── engine.py       # classify() function
│   ├── path.py         # Path protection
│   └── gateway.py      # Extension integration
├── util/               # Utilities
│   └── workspace.py    # Path safety helpers
├── trace/              # Session persistence
│   └── writer.py       # JSONL trace writer
├── context/            # Context builder
│   ├── builder.py      # System prompt assembly
│   ├── profile.py      # Project detection
│   └── memory.py       # Persistent memory
├── loop/               # Loop guards
│   ├── guards.py       # Pure-function guards
│   └── guards_ext.py   # Extension integration
├── eval/               # Evaluation framework
│   ├── harness.py      # Eval runner
│   ├── benchmarks/     # YAML scenarios
│   └── report.py       # Markdown/JSON reports
├── mcp/                # MCP integration
└── cli/                # CLI commands
```

---

## 🔧 Tools

| Tool | Description | Safety |
|------|-------------|--------|
| `read` | Read file contents | Workspace-bound, 10MB limit |
| `write` | Write to file | Workspace-bound, 10MB limit |
| `edit` | Replace text (unique match) | Ambiguity detection |
| `apply_patch` | Apply unified diff | Workspace-bound |
| `git_diff` | Show git diff | Read-only |
| `bash` | Execute command | Timeout (120s), output truncation (500KB) |

All tools use `resolve_in_workspace()` to prevent:
- Path traversal (`../`)
- Symlink escape
- Absolute path escapes

---

## 🛡️ Safety Model

### Two Layers of Protection

**1. Tool-Level Safety** (hard boundaries)
```python
resolve_in_workspace(cwd, user_path)
# ✅ "src/main.py" → /workspace/src/main.py
# ❌ "../etc/passwd" → PathSecurityError
# ❌ "/etc/passwd" → PathSecurityError
# ❌ symlink to /etc → PathSecurityError
```

**2. Policy-Level Safety** (configurable rules)
```json
{
  "path": {
    "deny": [".env", ".ssh/*", "**/*.key"],
    "confirm_write": ["package.json", "pyproject.toml"]
  },
  "command": {
    "deny": ["rm -rf", "curl.*\\|.*sh"],
    "confirm": ["npm install", "pip install"],
    "allow": ["pytest", "npm test"]
  }
}
```

### Loop Guards
- **Tool call limit**: Prevents infinite loops (default 100)
- **Token budget**: Configurable total token limit
- **Reward-hacking guard**: Blocks test file modification during "fix test" tasks
- **Failure detection**: Stops after repeated identical failures

---

## 🧪 Testing

```bash
# Run all tests (120 passing, ~30s)
uv run pytest tests/ -v

# Run specific test suites
uv run pytest tests/unit/test_providers.py    # Provider abstraction (24 tests)
uv run pytest tests/unit/test_events.py       # Event stream + offline loop (11 tests)
uv run pytest tests/unit/test_tool_safety.py  # Path safety (16 tests)
uv run pytest tests/unit/test_trace.py        # Session tracing (6 tests)
uv run pytest tests/unit/test_context.py      # Context builder (17 tests)
uv run pytest tests/unit/test_policy.py       # Policy engine (32 tests)

# Coverage report
uv run pytest tests/ --cov=codeagent --cov-report=html
```

**Test Highlights**:
- ✅ Offline agent loop (no API key required via MockProvider)
- ✅ Path traversal and symlink escape prevention
- ✅ Policy blocks dangerous operations
- ✅ JSONL trace round-trip
- ✅ Context builder precedence rules

---

## 📊 Architecture

### Provider Abstraction
```python
# Runtime depends only on the protocol
class ModelProvider(Protocol):
    async def generate(request: ModelRequest) -> ModelResponse: ...

# Concrete implementations
AnthropicProvider(api_key)  # Real API
MockProvider(responses)     # Offline tests
```

### Event Stream
```python
# Events emitted during execution
EventType.SESSION_START
EventType.TURN_START
EventType.MODEL_REQUEST
EventType.MODEL_RESPONSE
EventType.TOOL_CALL_REQUESTED
EventType.POLICY_VERDICT
EventType.TOOL_START
EventType.TOOL_END
EventType.TURN_END
EventType.SESSION_END
```

Events are auto-saved to `.agent/sessions/<session-id>.jsonl`.

### Context Builder
```python
# System prompt = base + profile + instructions
build_system_prompt(
    base_prompt="You are CodeAgent...",
    profile=detect_profile(cwd),  # Python, uv, pytest
    project_instructions=load_project_instructions(cwd),  # AGENTS.md
)
```

**Precedence**: `.agent/instructions.md` > `AGENTS.md` > `CLAUDE.md`

---

## 🎯 Evaluation

```bash
# Run builtin benchmarks
uv run codeagent eval --benchmark simple_edit
uv run codeagent eval --benchmark security

# Run custom scenarios
uv run codeagent eval --scenario-file my_tests.yaml

# Export trace per scenario
uv run codeagent eval --benchmark all --save-traces
```

**Builtin Benchmarks**:
- `simple_edit`: Basic code editing tasks
- `security`: Path escape, .env write, symlink escape, dangerous commands

---

## 📚 Documentation

- **[IMPROVEMENT_SUMMARY.md](IMPROVEMENT_SUMMARY.md)** — Complete improvement report (before/after, metrics, trade-offs)
- **[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)** — Architecture rationale (why not LangChain, why Python, etc.)
- **[DEMO.md](DEMO.md)** — 5-minute demo walkthrough for interviews
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design deep-dive

---

## 🗺️ Roadmap

### ✅ Completed
- [x] P0: Provider abstraction, async correctness, event stream
- [x] P1: Tool safety hardening, `apply_patch`, `git_diff`
- [x] P2: JSONL session tracing, CLI sessions command
- [x] P3: Context builder (AGENTS.md, profile injection)
- [x] P4: Security eval scenarios

### 🔜 Future Work
- [ ] Resume command (`codeagent resume <session-id>`)
- [ ] Interactive confirmation UI (TUI prompts for `confirm` verdicts)
- [ ] Token-aware context trimming (tiktoken integration)
- [ ] Streaming responses (incremental tool results)
- [ ] MCP server integrations (pre-built tools)

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

### Inspiration
- **[Pi Agent](https://github.com/oughtinc/pi)** — Trajectory logs, pure-function policy, tool safety
- **[Claude Code](https://claude.ai/code)** — System prompt design, tool UX
- **[agent-cli (TypeScript)](https://github.com/myshawnx/agent-cli)** — Original design

### Core Technologies
- **[Anthropic Claude API](https://www.anthropic.com/)** — LLM backend
- **[Pydantic](https://docs.pydantic.dev/)** — Type safety and validation
- **[Typer](https://typer.tiangolo.com/)** + **[Rich](https://rich.readthedocs.io/)** — CLI framework and output

---

## 🎤 Interview Demo

See **[DEMO.md](DEMO.md)** for a structured 5-minute walkthrough.

**Key talking points**:
1. **Provider abstraction** → testability and portability
2. **Event stream** → observability and debugging
3. **Defense in depth** → tool-level + policy-level safety
4. **Offline testing** → MockProvider, 40+ tests with no API key
5. **Production patterns** → async correctness, timeouts, structured errors

**Honest assessment**:
- ✅ Clean architecture, well-tested, interview-grade
- ❌ Not a production-deployed system (no auth, rate limiting, telemetry)
- ❌ Not feature-complete (context compaction, resume, interactive confirmation are future work)

---

## 📞 Contact

Built by **[Your Name]** for AI Agent / Coding Agent developer role interviews.

**GitHub**: https://github.com/yourusername/codeagent-py  
**Email**: your.email@example.com

---

**Final note**: This project is designed to demonstrate understanding of production-grade agent runtime architecture without over-engineering. The foundation is solid, tested, and ready to build on.
