"""策略引擎类型定义"""

from typing import Literal

from pydantic import BaseModel

from ..config.schema import ApprovalMode, PolicyConfig


class ToolCallEvent(BaseModel):
    """工具调用事件"""
    tool_name: str
    input: dict


class AllowVerdict(BaseModel):
    """允许判决"""
    kind: Literal["allow"] = "allow"


class ConfirmVerdict(BaseModel):
    """需要确认判决"""
    kind: Literal["confirm"] = "confirm"
    reason: str


class DenyVerdict(BaseModel):
    """拒绝判决"""
    kind: Literal["deny"] = "deny"
    reason: str


# 联合类型
Verdict = AllowVerdict | ConfirmVerdict | DenyVerdict


class ClassifyOptions(BaseModel):
    """分类选项"""
    repo_root: str
    changed_files: int = 0
