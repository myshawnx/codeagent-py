"""策略引擎核心 - classify() 纯函数"""

from ..config.schema import ApprovalMode, PolicyConfig
from .command import classify_command
from .path import (
    bash_touches_protected_path,
    outside_repo_root,
    path_confirm_write,
    path_denied,
    target_path,
)
from .types import (
    AllowVerdict,
    ClassifyOptions,
    ConfirmVerdict,
    DenyVerdict,
    ToolCallEvent,
    Verdict,
)

# 工具分类
READ_TOOLS = {"read", "grep", "find", "ls"}
WRITE_TOOLS = {"write", "edit", "apply_patch"}


def classify(
    event: ToolCallEvent,
    mode: ApprovalMode,
    policy: PolicyConfig,
    opts: ClassifyOptions,
) -> Verdict:
    """
    核心分类函数：决定工具调用是 allow/confirm/deny
    
    这是策略引擎的唯一入口，纯函数，无副作用
    """
    tool_name = event.tool_name
    
    # 读工具
    if tool_name in READ_TOOLS:
        return _classify_read(event, policy, opts)
    
    # 写工具
    if tool_name in WRITE_TOOLS:
        return _classify_write(event, mode, policy, opts)
    
    # bash 工具
    if tool_name == "bash":
        return _classify_bash(event, mode, policy)
    
    # 未知工具默认需要确认（保守策略）
    return ConfirmVerdict(reason=f"Unknown tool requires confirmation: {tool_name}")


def _classify_read(
    event: ToolCallEvent,
    policy: PolicyConfig,
    opts: ClassifyOptions,
) -> Verdict:
    """分类读工具"""
    path = target_path(event.input)
    
    # find 工具没有指定路径时默认为当前目录
    if event.tool_name == "find" and not path:
        path = "."
    
    if not path:
        return AllowVerdict()
    
    # 检查是否在仓库外
    if outside_repo_root(path, opts.repo_root):
        return DenyVerdict(reason=f"Read outside repo root: {path}")
    
    # 检查是否是受保护路径
    if path_denied(path, policy.path):
        return DenyVerdict(reason=f"Protected path: {path}")
    
    return AllowVerdict()


def _classify_write(
    event: ToolCallEvent,
    mode: ApprovalMode,
    policy: PolicyConfig,
    opts: ClassifyOptions,
) -> Verdict:
    """分类写工具"""
    # readonly 模式直接拒绝
    if mode == ApprovalMode.READONLY:
        return DenyVerdict(reason=f"readonly mode blocks {event.tool_name}")
    
    path = target_path(event.input)
    if not path:
        return ConfirmVerdict(reason=f"{event.tool_name} target path is unknown")
    
    # 检查是否是受保护路径（硬拒绝）
    if path_denied(path, policy.path):
        return DenyVerdict(reason=f"Protected path: {path}")
    
    # 检查是否在仓库外
    if outside_repo_root(path, opts.repo_root):
        return ConfirmVerdict(reason=f"Outside repo root: {path}")
    
    # 检查是否是敏感路径（需确认）
    if path_confirm_write(path, policy.path):
        return ConfirmVerdict(reason=f"Sensitive write target: {path}")
    
    # 检查文件修改数量限制
    if opts.changed_files >= policy.limits.max_changed_files:
        return ConfirmVerdict(
            reason=f"Changed files limit reached ({policy.limits.max_changed_files})"
        )
    
    # suggest 模式需要确认
    if mode == ApprovalMode.SUGGEST:
        return ConfirmVerdict(reason=f"suggest mode requires confirmation before {event.tool_name}")
    
    # 通过所有检查
    return AllowVerdict()


def _classify_bash(
    event: ToolCallEvent,
    mode: ApprovalMode,
    policy: PolicyConfig,
) -> Verdict:
    """分类 bash 工具"""
    # readonly 模式直接拒绝
    if mode == ApprovalMode.READONLY:
        return DenyVerdict(reason="readonly mode blocks bash")
    
    command = event.input.get("command", "")
    if not isinstance(command, str):
        return DenyVerdict(reason="Invalid bash command")
    
    # 使用命令分类器
    tier = classify_command(command, policy.command)
    
    if tier == "deny":
        return DenyVerdict(reason=f"High-risk command: {command}")
    
    # 检查是否可能写入受保护路径
    if bash_touches_protected_path(command, policy.path):
        return ConfirmVerdict(reason=f"Bash touches protected path: {command}")
    
    if tier == "confirm":
        return ConfirmVerdict(reason=f"Command requires confirmation: {command}")
    
    # tier == "allow"
    return AllowVerdict()


def is_write_like_tool(tool_name: str) -> bool:
    """检查是否是写类工具"""
    return tool_name in WRITE_TOOLS
