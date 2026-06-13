"""循环护栏类型定义"""

from pydantic import BaseModel

from ..config.schema import ProjectProfile


class LoopGuardOptions(BaseModel):
    """循环护栏选项"""
    goal: str = ""
    max_tool_calls: int = 100
    max_fix_iterations: int = 3
    token_budget: int | None = None
    command_timeout_ms: int = 120_000
    profile: ProjectProfile | None = None


class LoopGuardState(BaseModel):
    """循环护栏状态"""
    goal: str = ""
    tool_calls: int = 0
    blocked: bool = False
    token_budget_exceeded: bool = False
    total_tokens: int = 0
    repeated_failures: int = 0
    last_failure_signature: str | None = None
