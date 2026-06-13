"""策略网关 - 扩展系统集成"""

from ..config.schema import ApprovalMode, PolicyConfig
from ..runtime.extensions import Extension, ExtensionAPI
from .engine import classify
from .types import ClassifyOptions, ToolCallEvent


class PolicyGateway(Extension):
    """策略网关扩展"""

    def __init__(
        self,
        policy: PolicyConfig,
        mode: ApprovalMode,
        repo_root: str,
    ):
        self.policy = policy
        self.mode = mode
        self.repo_root = repo_root
        self.changed_files = 0

    def on_session_start(self, api: ExtensionAPI) -> None:
        """会话开始时重置状态"""
        self.changed_files = 0

    def on_tool_call(self, api: ExtensionAPI, tool_name: str, tool_input: dict) -> dict | None:
        """工具调用前进行策略检查"""
        # 构造事件
        event = ToolCallEvent(tool_name=tool_name, input=tool_input)

        # 分类选项
        opts = ClassifyOptions(
            repo_root=self.repo_root,
            changed_files=self.changed_files,
        )

        # 执行分类
        verdict = classify(event, self.mode, self.policy, opts)

        # 记录
        api.append_entry("policy-check", {
            "tool": tool_name,
            "verdict": verdict.kind,
            "reason": verdict.reason if hasattr(verdict, "reason") else None,
        })

        # 处理判决
        if verdict.kind == "deny":
            api.append_entry("policy-deny", {
                "tool": tool_name,
                "reason": verdict.reason,
            })
            return {"block": True, "reason": verdict.reason}

        if verdict.kind == "confirm":
            # 简化实现：auto 模式下 confirm 也放行
            # 完整实现需要 UI 交互
            if self.mode == ApprovalMode.AUTO:
                pass  # 放行
            else:
                # 非 auto 模式下，confirm 暂时也放行（简化）
                # TODO: P2 阶段实现 UI 确认
                api.append_entry("policy-confirm-bypassed", {
                    "tool": tool_name,
                    "reason": verdict.reason,
                })

        # 更新文件计数
        if tool_name in ["write", "edit"]:
            self.changed_files += 1

        return None  # 允许继续
