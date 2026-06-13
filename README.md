# CodeAgent (Python)

> 本地优先的 CLI 编码助手 - 从 [agent-cli](https://github.com/myshawnx/agent-cli) (TypeScript) 迁移到 Python

## 项目状态

🚧 **开发中** - 正在从 TypeScript 迁移到 Python

- ✅ 项目初始化
- ⏳ P0: 策略引擎和循环护栏
- ⏳ P1: Agent 运行时
- ⏳ P2: CLI 和 MCP 集成
- ⏳ P3: 评测框架

## 核心价值

1. **策略引擎** - 声明式安全层（readonly/suggest/workspace-write/auto 四种模式）
2. **循环护栏** - 预算控制、反作弊、无进展检测
3. **MCP 集成** - 外部工具生态（stdio JSON-RPC）
4. **评测框架** - 确定性回归测试
5. **项目画像** - 自动探测项目结构

## 技术栈

- **包管理**: uv
- **类型系统**: Pydantic v2
- **CLI**: Typer + Rich
- **LLM SDK**: Anthropic Python SDK
- **测试**: pytest
- **异步**: asyncio

## 快速开始（开发中）

```bash
# 安装依赖
uv sync --dev

# 运行测试
uv run pytest

# 运行 CLI（开发中）
uv run codeagent --help
```

## 开发

```bash
# 安装开发依赖
uv sync --dev

# 运行测试
uv run pytest

# 类型检查
uv run mypy src

# 代码格式化
uv run ruff format src tests

# 代码检查
uv run ruff check src tests
```

## 架构

详见 [ARCHITECTURE.md](ARCHITECTURE.md)（待完成）

## 迁移说明

详见 [MIGRATION.md](MIGRATION.md)（待完成）

## License

MIT - 见 [LICENSE](LICENSE)
