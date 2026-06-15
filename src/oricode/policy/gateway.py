"""策略网关 - 扩展系统集成"""

from ..config.schema import ApprovalMode, PolicyConfig
from ..runtime.events import EventType
from ..runtime.extensions import Extension, ExtensionAPI
from .approval import (
    ApprovalHandler,
    ApprovalRequest,
    AutoApprovalHandler,
)
from .engine import classify
from .types import ClassifyOptions, ToolCallEvent


class PolicyGateway(Extension):
    """策略网关扩展"""

    def __init__(
        self,
        policy: PolicyConfig,
        mode: ApprovalMode,
        repo_root: str,
        approval_handler: ApprovalHandler | None = None,
    ):
        self.policy = policy
        self.mode = mode
        self.repo_root = repo_root
        self.approval_handler = approval_handler or AutoApprovalHandler()
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
            request = ApprovalRequest(
                tool_name=tool_name,
                tool_input=tool_input,
                reason=verdict.reason,
            )
            api.append_entry("approval-requested", {
                "tool": tool_name,
                "reason": verdict.reason,
            })
            api.emit_event(EventType.APPROVAL_REQUESTED, {
                "tool": tool_name,
                "input": tool_input,
                "reason": verdict.reason,
            })

            decision = self.approval_handler.approve(request)
            api.append_entry("approval-decision", {
                "tool": tool_name,
                "approved": decision.approved,
                "reason": decision.reason,
            })
            api.emit_event(EventType.APPROVAL_DECISION, {
                "tool": tool_name,
                "approved": decision.approved,
                "reason": decision.reason,
            })

            if not decision.approved:
                reason = decision.reason or verdict.reason
                return {"block": True, "reason": f"Approval denied: {reason}"}

        # 更新文件计数
        if tool_name in ["write", "edit"]:
            self.changed_files += 1

        return None  # 允许继续
