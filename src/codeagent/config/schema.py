"""配置和类型定义 - Pydantic 模型"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ApprovalMode(str, Enum):
    """审批模式"""
    READONLY = "readonly"
    SUGGEST = "suggest"
    WORKSPACE_WRITE = "workspace-write"
    AUTO = "auto"


class CommandPolicy(BaseModel):
    """命令策略配置"""
    allow: list[str] = Field(default_factory=list, description="允许的命令模式")
    confirm: list[str] = Field(default_factory=list, description="需要确认的命令模式")
    deny: list[str] = Field(default_factory=list, description="拒绝的命令模式")


class PathPolicy(BaseModel):
    """路径策略配置"""
    deny: list[str] = Field(default_factory=list, description="拒绝访问的路径（glob 模式）")
    confirm_write: list[str] = Field(default_factory=list, description="需要确认写入的路径（glob 模式）")


class LimitsConfig(BaseModel):
    """限制配置"""
    max_changed_files: int = Field(default=50, description="最大修改文件数")
    max_fix_iterations: int = Field(default=3, description="最大修复迭代次数")
    max_tool_calls: int = Field(default=100, description="最大工具调用次数")
    token_budget: int | None = Field(default=None, description="Token 预算")
    command_timeout_ms: int = Field(default=120_000, description="命令超时（毫秒）")


class SandboxConfig(BaseModel):
    """沙箱配置（预留）"""
    enabled: bool = Field(default=False, description="是否启用沙箱")
    # v0.1 预留字段，未接入真实沙箱


class PolicyConfig(BaseModel):
    """策略配置"""
    command: CommandPolicy = Field(default_factory=CommandPolicy)
    path: PathPolicy = Field(default_factory=PathPolicy)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)


class ProjectProfile(BaseModel):
    """项目画像"""
    language: str = Field(description="编程语言")
    package_manager: str = Field(description="包管理器")
    framework: str | None = Field(default=None, description="框架")
    test_framework: str | None = Field(default=None, description="测试框架")
    source_dirs: list[str] = Field(default_factory=list, description="源码目录")
    test_dirs: list[str] = Field(default_factory=list, description="测试目录")
    commands: dict[str, str] = Field(default_factory=dict, description="常用命令（test/lint/build）")


class AgentConfig(BaseModel):
    """Agent 配置（.agent/ 目录的聚合）"""
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    profile: ProjectProfile | None = Field(default=None)
    
    class Config:
        extra = "allow"  # 允许额外字段
