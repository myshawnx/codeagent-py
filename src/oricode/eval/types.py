"""评测框架类型定义"""

from typing import Literal

from pydantic import BaseModel, Field


class ScenarioFile(BaseModel):
    """场景文件"""
    path: str
    content: str


class Scenario(BaseModel):
    """评测场景"""
    name: str = Field(description="场景名称")
    description: str = Field(description="场景描述")
    prompt: str = Field(description="发给 Agent 的提示")
    input_files: dict[str, str] = Field(default_factory=dict, description="输入文件 {路径: 内容}")
    expected_files: dict[str, str] = Field(default_factory=dict, description="期望输出文件 {路径: 内容}")
    expected_changed_files: list[str] = Field(
        default_factory=list,
        description="Expected files that should be changed or created",
    )
    forbidden_files: list[str] = Field(
        default_factory=list,
        description="Files or glob patterns that must not be changed",
    )
    test_commands: list[str] = Field(
        default_factory=list,
        description="Trusted commands to run after the agent finishes",
    )
    scoring: dict[str, float] = Field(default_factory=dict, description="评分规则")
    timeout_sec: int = Field(default=60, description="超时时间（秒）")
    model: str = Field(default="claude-sonnet-4-6", description="使用的模型")


class ScoringRule(BaseModel):
    """评分规则"""
    type: Literal["file_exact", "file_contains", "file_regex", "test_pass", "custom"]
    weight: float = 1.0
    params: dict = Field(default_factory=dict)


class EvalMetrics(BaseModel):
    """Structured metrics collected from files and runtime events."""

    tests_passed: bool | None = None
    expected_files_changed: bool = False
    forbidden_files_touched: bool = False
    dangerous_commands_blocked: bool = False
    tool_calls: int = 0
    tokens: int = 0
    duration_ms: int = 0
    changed_files: list[str] = Field(default_factory=list)


class ScenarioResult(BaseModel):
    """场景结果"""
    scenario_name: str
    success: bool
    score: float  # 0.0 - 1.0
    duration_sec: float
    output_files: dict[str, str]
    error: str | None = None
    details: dict = Field(default_factory=dict)
    metrics: EvalMetrics = Field(default_factory=EvalMetrics)


class BenchmarkReport(BaseModel):
    """基准测试报告"""
    total_scenarios: int
    passed: int
    failed: int
    average_score: float
    total_duration_sec: float
    results: list[ScenarioResult]
    model: str
    timestamp: str
