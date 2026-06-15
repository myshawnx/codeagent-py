# OriCode

[English README](README_EN.md)

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-165%20passing-brightgreen.svg)](#测试)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**OriCode 是一个 Python-first、本地优先的 Coding Agent Runtime。**

它的重点不是做一个完整商业编码助手，而是把 Coding Agent 的底层运行机制拆成可读、可测、可扩展的模块：模型 Provider、Agent Loop、工具调用、策略审批、本地安全执行、事件流、JSONL Trace、Session Resume、Eval Harness 和 MCP stdio 集成。

---

## 功能

OriCode 可以在本地 workspace 中执行一个受控的 coding-agent 循环：

```text
用户任务
  -> 构建项目上下文
  -> 调用模型 Provider
  -> 解析文本或工具调用
  -> 经过 Policy Gateway 审批
  -> 执行本地工具
  -> 将工具结果回传给模型
  -> 记录事件和 JSONL Trace
  -> 支持从 Trace 继续会话
```

主要功能：

| 能力 | 状态 | 说明 |
|---|---:|---|
| Provider 抽象 | 已实现 | Runtime 依赖标准化 `ModelProvider`，不直接绑定 SDK 对象 |
| AnthropicProvider | 已实现 | 通过 Anthropic Python SDK 调用 Claude |
| MockProvider | 已实现 | 离线测试完整 Agent Loop，不消耗 API 调用 |
| Tool Calling | 已实现 | 标准化 `tool_use` / `tool_result` |
| Streaming | 已实现 | Provider-neutral stream events，CLI 支持 `--stream` |
| 本地文件工具 | 已实现 | `read`、`write`、`edit`、`apply_patch`、`git_diff` |
| Bash 工具 | 已实现 | timeout、输出截断、非零退出处理 |
| 工具安全 | 已实现 | 阻止路径穿越、绝对路径逃逸、symlink escape |
| Policy Gateway | 已实现 | 支持 allow / confirm / deny |
| Approval Handler | 已实现 | 支持 Rich prompt、auto、deny、recording handler |
| Loop Guards | 已实现 | 限制工具调用、token budget、重复失败、reward hacking |
| EventBus | 已实现 | 统一记录 model、tool、policy、session、error 事件 |
| JSONL Trace | 已实现 | 保存到 `.agent/sessions/<session_id>.jsonl` |
| Resume | 已实现 | 从 Trace 重建 normalized messages 并继续会话 |
| Eval Harness | 已实现 | YAML 场景、结构化指标、报告和 trace export |
| MCP stdio | 基础可用 | filesystem / GitHub presets，env credentials |
| 并发只读工具 | 已实现 | `parallel_safe` 工具可并发执行并保持结果顺序 |
| 读缓存 | 已实现 | 按 mtime / size 校验，写入后失效 |

当前测试结果：

```text
165 passed, 4 skipped
```

---

## 和主流 Coding Agent 的区别

| 项目 | 主要定位 | 更强的地方 | OriCode 的区别 |
|---|---|---|---|
| Claude Code | 成熟商业 coding assistant，覆盖 terminal、IDE、desktop、web 等使用场景 | 产品体验、真实编码效果、生态集成、权限交互、远程/多端工作流 | OriCode 不追求产品完整度，更强调 runtime 内部实现可见、可测、可改 |
| OpenAI Codex | OpenAI 的 coding-agent 产品和平台能力，包含模型、SDK、CLI、沙箱、工作流、子代理等方向 | 平台能力、模型能力、托管环境、规模化工作流和生态 | OriCode 是本地 Python runtime，不依赖托管平台，更适合研究 Agent Loop 和安全边界 |
| OpenCode | 开源 AI coding agent，提供 terminal/TUI、desktop、IDE 等形态 | 用户侧体验更完整，开源生态更成熟，多 provider 配置更丰富 | OriCode 更小，更偏 Python runtime 参考实现，重点在模块边界、测试和 trace |
| Pi Agent / trajectory-style agents | 偏 agent framework、trajectory、policy、eval 等概念启发 | 抽象层和研究味更强，适合探索 agent 行为建模 | OriCode 更贴近本地代码仓库操作，实现了文件、bash、policy、trace、eval 的具体闭环 |
| OriCode | Python-first、本地优先 coding-agent runtime | 结构清晰、离线可测、安全边界显式、JSONL trace 可检查、适合二次开发 | 不提供成熟 UI、云端 sandbox、商业权限系统、多端同步或生产级托管 |

一句话总结：

```text
Claude Code / Codex / OpenCode 更像可直接使用的产品或平台；
OriCode 更像一个把 coding-agent runtime 拆开给你看的 Python 参考实现。
```

---

## 架构

```text
CLI
  -> AgentSession
    -> Context Builder
    -> AgentLoop
      -> ModelProvider
        -> AnthropicProvider
        -> MockProvider
      -> Tool Registry
        -> read / write / edit / apply_patch / git_diff / bash
      -> Extensions
        -> PolicyGateway
        -> LoopGuards
      -> EventBus
        -> InMemorySink
        -> ConsoleSink
        -> TraceWriter
```

目录结构：

```text
src/oricode/
├── providers/          模型 Provider 抽象和具体实现
├── runtime/            AgentLoop、AgentSession、工具、事件、扩展点
├── policy/             策略引擎、策略网关、审批处理器
├── loop/               工具调用限制、token budget、失败检测、防作弊
├── context/            项目 profile、项目说明、系统提示词构建
├── trace/              JSONL trace 持久化和会话恢复
├── eval/               YAML eval harness、benchmark、报告和指标
├── mcp/                stdio MCP client 和 preset 配置
├── util/               workspace 路径安全工具
└── cli/                Typer CLI 命令
```

---

## 快速开始

### 安装

```bash
git clone https://github.com/myshawnx/oricode.git
cd oricode
uv sync
```

### 配置模型

真实模型调用需要 Anthropic API key：

```bash
export ANTHROPIC_API_KEY=your-key-here
```

初始化项目配置：

```bash
uv run oricode init
```

### 运行任务

```bash
uv run oricode ask "Explain this codebase" --mode readonly
uv run oricode ask "Fix the bug in src/example.py" --mode workspace-write
uv run oricode ask "Explain this codebase" --mode readonly --stream
```

### Session 和 Resume

```bash
uv run oricode sessions
uv run oricode sessions <session-id>
uv run oricode resume <session-id> "continue from here"
```

### Eval

```bash
uv run oricode eval --benchmark simple_edit
uv run oricode eval --benchmark security
uv run oricode eval --benchmark all
```

### MCP

```bash
uv run oricode mcp presets
uv run oricode mcp add filesystem
uv run oricode mcp add github
uv run oricode mcp list
```

---

## 测试

运行完整测试：

```bash
uv run pytest
```

重点测试：

```bash
uv run pytest tests/unit/test_events.py -q
uv run pytest tests/unit/test_tool_safety.py -q
uv run pytest tests/unit/test_trace.py -q
uv run pytest tests/unit/test_policy.py -q
uv run pytest tests/unit/test_eval.py -q
```

测试覆盖：

- Provider normalization
- MockProvider 离线 Agent Loop
- streaming events
- tool use / tool result round trip
- policy verdict 和 approval events
- workspace path safety
- bash timeout
- JSONL trace 读写和 resume
- YAML eval scoring

---

## 优点

- **本地优先**：工具执行、权限判断、trace 都发生在本地 workspace，容易观察和调试。
- **模块清晰**：Provider、AgentLoop、Tool Registry、PolicyGateway、EventBus、TraceWriter、EvalHarness 分层明确。
- **离线可测**：MockProvider 可以完整模拟模型行为，核心 loop 不依赖真实 API。
- **安全边界显式**：policy 决策和工具层硬限制分开，路径逃逸和 symlink escape 会被工具层阻止。
- **可观测性好**：所有关键运行步骤都有事件，JSONL trace 可用于排查和恢复。
- **Eval 友好**：YAML scenarios 可以固定输入、期望文件、禁止文件、post-run tests 和评分指标。
- **适合二次开发**：新增 provider、tool、policy、event sink 或 MCP extension 的入口比较明确。

---

## 缺点与限制

- **不是完整产品**：没有成熟 TUI、IDE 插件、桌面端、账号体系、团队协作、计费或托管任务系统。
- **不是强隔离 sandbox**：当前主要是 workspace 级别和工具级别防护，没有容器/虚拟机/OS-level sandbox。
- **Provider 较少**：真实 provider 目前主要是 Anthropic；OpenAI、Gemini、本地模型等需要继续补。
- **Resume 是线性的**：支持从 JSONL trace 继续，但还没有 fork/tree session 或 trajectory graph。
- **MCP 是基础版**：已有 stdio presets，但没有完整 marketplace、health check、安装引导和凭证 UI。
- **Eval 偏回归测试**：适合验证工具行为和安全阻断，不等同于大规模模型质量 benchmark。
- **UI 较轻**：CLI 可用，但没有 diff review、plan view、权限弹窗、任务队列等成熟交互。

---

## 适合和不适合

适合：

- 学习或改造 coding-agent runtime。
- 构建本地 Agent 工具调用原型。
- 研究 policy、tool safety、trace、eval 的工程边界。
- 作为更大 Agent 产品的 Python runtime 参考。

不适合：

- 直接替代 Claude Code、Codex、OpenCode、Cursor 等成熟编码助手。
- 在不可信代码上做强隔离自动执行。
- 直接接入生产仓库做高可靠自动改代码。
- 承担需要团队权限、审计、计费、托管调度的生产工作负载。

---

## 后续方向

- 容器级 sandbox 和文件系统 diff 捕获
- OpenAI / Gemini / local model providers
- fork/tree session 和 trajectory replay
- 更完整的 MCP server lifecycle
- OpenTelemetry exporter
- TUI diff review 和权限交互

---

## 文档

- [README_EN.md](README_EN.md)：英文 README
- [ARCHITECTURE.md](ARCHITECTURE.md)：系统架构
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)：设计取舍
- [DEMO.md](DEMO.md)：演示脚本
- [IMPROVEMENT_SUMMARY.md](IMPROVEMENT_SUMMARY.md)：改进总结
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)：项目概览
- [UPDATE_SUMMARY.md](UPDATE_SUMMARY.md)：阶段更新
- [MIGRATION.md](MIGRATION.md)：迁移说明

---

## License

MIT License.
