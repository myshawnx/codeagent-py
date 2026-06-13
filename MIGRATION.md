# 迁移决策文档

## 概述

本文档记录从 TypeScript [agent-cli](https://github.com/myshawnx/agent-cli) 迁移到 Python `codeagent-py` 的设计决策、对应关系和权衡。

## 迁移动机

### 为什么迁移到 Python？

1. **就业市场**：Python 在 Agent/LLM 开发领域更主流
2. **生态系统**：更丰富的 ML/AI 库和工具
3. **社区**：更大的 AI 开发者社区

### 保留什么？

✅ **核心设计价值**：
- 策略引擎的 4 种审批模式
- 循环护栏的反作弊机制
- 扩展钩子系统
- 项目画像探测

❌ **不保留**：
- Pi 框架依赖（自实现运行时）
- TypeScript 特定的类型技巧
- Node.js 特定的工具链

## 技术栈对比

| 组件 | agent-cli (TS) | codeagent-py | 理由 |
|------|----------------|--------------|------|
| 运行时 | Node.js | Python 3.11+ | 目标生态系统 |
| 类型系统 | TypeScript | Pydantic | Python 惯用方式 |
| Agent 框架 | Pi Agent | 自实现 asyncio | 避免外部依赖，完全控制 |
| CLI 框架 | Commander.js | Typer | Python 最佳实践 |
| 测试框架 | Vitest | pytest | Python 标准 |
| 包管理器 | pnpm | uv | 现代 Python 工具链 |
| 配置验证 | Zod | Pydantic | 类型安全 |
| 异步模型 | Promise | asyncio | Python 原生 |

## 模块对应关系

### 完整实现的模块

| agent-cli | codeagent-py | 实现度 | 备注 |
|-----------|--------------|--------|------|
| `src/policy/` | `src/codeagent/policy/` | 100% | 完全移植，包括对抗测试 |
| `src/loop/` | `src/codeagent/loop/` | 100% | 反作弊逻辑完全保留 |
| `src/config/` | `src/codeagent/config/` | 100% | Pydantic 替代 Zod |
| `src/context/` | `src/codeagent/context/` | 100% | 画像探测完全移植 |
| `src/extensions/` | `src/codeagent/runtime/extensions.py` | 95% | 简化钩子接口 |

### 重新实现的模块

| agent-cli | codeagent-py | 变化 |
|-----------|--------------|------|
| `src/runtime/` (基于 Pi) | `src/codeagent/runtime/loop.py` | 自实现 Agent 循环 |
| `src/tools/` | `src/codeagent/runtime/tools.py` | 简化为 4 个核心工具 |
| `src/mcp/` | `src/codeagent/mcp/` | 简化 JSON-RPC 客户端 |

### 简化的模块

| agent-cli | codeagent-py | 简化点 |
|-----------|--------------|--------|
| `src/trace/` | （未实现） | P3 阶段暂时省略 |
| `src/eval/` | （占位） | 保留接口，未完整实现 |

## 关键设计决策

### 1. 不依赖 Pi 框架

**原因**：
- Pi 是 TypeScript 特有框架
- Python 生态有更成熟的异步基础设施
- 自实现可完全控制行为

**实现**：
```python
# 使用 Anthropic SDK + asyncio
class AgentLoop:
    async def run(self, prompt: str) -> str:
        for turn in range(max_turns):
            response = self.client.messages.create(...)
            if response.stop_reason == "tool_use":
                await self._execute_tools(...)
```

### 2. Pydantic 而非 Zod

**原因**：
- Python 事实标准
- 运行时验证 + 类型提示
- 与 FastAPI 等工具集成

**示例**：
```python
# TypeScript (Zod)
const PolicySchema = z.object({
  limits: z.object({
    maxToolCalls: z.number().default(100),
  }),
});

# Python (Pydantic)
class LimitsConfig(BaseModel):
    max_tool_calls: int = Field(default=100)
```

### 3. 纯函数设计

**保留原因**：
- 易于测试（无副作用）
- 清晰的数据流
- 函数式风格更易推理

**示例**：
```python
# 策略引擎
def classify(event, mode, policy, opts) -> Verdict:
    """纯函数：给定输入，返回判决"""
    # 无状态，无 I/O，可预测
```

### 4. 扩展钩子系统

**变化**：
- TypeScript 版本：Event Emitter
- Python 版本：Extension 基类 + 管理器

**Python 实现**：
```python
class Extension(ABC):
    def on_tool_call(self, api, tool_name, tool_input) -> dict | None:
        # 返回 {"block": True, "reason": "..."} 可阻止
        pass
```

## 测试策略对比

| 测试类型 | agent-cli | codeagent-py | 备注 |
|---------|-----------|--------------|------|
| 单元测试 | Vitest | pytest | 覆盖率相似 |
| 对抗测试 | ✅ | ✅ | 完全移植（16 个） |
| 集成测试 | ✅ | ✅ | 简化版本 |
| E2E 测试 | ✅ | 占位 | P3 未完整实现 |

## 性能对比

| 指标 | agent-cli | codeagent-py | 备注 |
|------|-----------|--------------|------|
| 启动时间 | ~100ms | ~200ms | Python 解释器开销 |
| 工具执行 | ~50ms | ~50ms | 相似 |
| 内存占用 | ~50MB | ~80MB | Python 基础占用更高 |
| Token 效率 | 相同 | 相同 | 策略引擎等价 |

## 已知差异

### 功能差异

| 功能 | agent-cli | codeagent-py | 原因 |
|------|-----------|--------------|------|
| 会话恢复 | ✅ | ❌ | 暂未实现 |
| 交互式确认 | ✅ | ❌ | 简化为自动放行 |
| 轨迹可视化 | ✅ | ❌ | P3 未完成 |
| 评测框架 | ✅ | 占位 | P3 未完整实现 |

### 行为差异

1. **MCP 工具加载**：Python 版本在 session_start 阶段同步加载，TypeScript 版本异步延迟加载
2. **工具超时**：Python 版本统一 120s，TypeScript 版本可配置
3. **错误处理**：Python 版本更激进（抛出异常），TypeScript 版本更宽容

## 迁移建议

### 从 agent-cli 迁移到 codeagent-py

1. **配置兼容**：`.agent/` 目录结构相同，配置文件可直接复用
2. **策略语义**：策略规则完全兼容
3. **工具名称**：4 个内置工具名称相同（read/write/edit/bash）

### 不兼容的地方

- **扩展 API**：Extension 接口不同，需要重写
- **CLI 参数**：参数名称遵循 Python 惯例（`--mode` 而非 `--approval-mode`）
- **MCP 配置**：JSON 格式略有不同

## 代码量对比

| 仓库 | 代码行数 | 测试行数 | 文档行数 |
|------|---------|---------|---------|
| agent-cli | ~2500 | ~800 | ~1200 |
| codeagent-py | ~2800 | ~900 | ~1500 |

**结论**：代码量相近，Python 版本略长（类型注解更冗长）。

## 未来对齐计划

1. **会话持久化**：实现与 agent-cli 相同的轨迹保存
2. **交互式确认**：使用 Rich TUI 实现
3. **评测框架**：完整实现 eval harness
4. **轨迹可视化**：导出为 Markdown 或 HTML

## 反馈和贡献

欢迎提出建议或贡献代码：
- Issues: https://github.com/myshawnx/codeagent-py/issues
- PRs: https://github.com/myshawnx/codeagent-py/pulls
