"""评测运行器 - 确定性、离线评测"""

import asyncio
import fnmatch
import json
import re
import shlex
import tempfile
import time
from datetime import datetime
from pathlib import Path
from subprocess import TimeoutExpired, run

from ..config.schema import ApprovalMode, CommandPolicy, PathPolicy, PolicyConfig
from ..loop.guards_ext import LoopGuardsExtension
from ..loop.types import LoopGuardOptions
from ..policy.approval import DenyApprovalHandler
from ..policy.gateway import PolicyGateway
from ..runtime.events import Event, EventBus, EventType
from ..runtime.session import AgentSession
from .scoring import score_scenario
from .types import BenchmarkReport, EvalMetrics, Scenario, ScenarioResult


class EvalHarness:
    """评测运行器"""

    def __init__(
        self,
        api_key: str | None = None,
        save_traces: bool = False,
        trace_dir: str | Path | None = None,
    ):
        self.api_key = api_key
        self.save_traces = save_traces
        self.trace_dir = Path(trace_dir) if trace_dir is not None else None
    
    async def run_scenario(self, scenario: Scenario) -> ScenarioResult:
        """运行单个场景"""
        start_time = time.time()
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                # 准备输入文件
                for path, content in scenario.input_files.items():
                    file_path = Path(tmpdir) / path
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")

                before_snapshot = snapshot_workspace(Path(tmpdir))
                
                # 创建 Agent 会话
                event_bus = EventBus()
                session = AgentSession(
                    cwd=tmpdir,
                    api_key=self.api_key,
                    model=scenario.model,
                    extensions=build_eval_extensions(scenario, tmpdir),
                    event_bus=event_bus,
                )
                
                # 运行 Agent
                try:
                    await asyncio.wait_for(
                        session.run(scenario.prompt),
                        timeout=scenario.timeout_sec,
                    )
                except asyncio.TimeoutError:
                    duration = time.time() - start_time
                    return ScenarioResult(
                        scenario_name=scenario.name,
                        success=False,
                        score=0.0,
                        duration_sec=duration,
                        output_files={},
                        error=f"Timeout after {scenario.timeout_sec}s",
                        metrics=EvalMetrics(duration_ms=int(duration * 1000)),
                    )

                after_snapshot = snapshot_workspace(Path(tmpdir))
                tests_passed, test_details = run_test_commands(
                    Path(tmpdir),
                    scenario.test_commands,
                    scenario.timeout_sec,
                )
                
                # 收集输出文件
                output_files = {}
                for expected_path in scenario.expected_files.keys():
                    file_path = Path(tmpdir) / expected_path
                    if file_path.exists():
                        output_files[expected_path] = file_path.read_text(encoding="utf-8")

                duration = time.time() - start_time
                metrics = build_eval_metrics(
                    scenario,
                    before_snapshot,
                    after_snapshot,
                    event_bus.events,
                    duration,
                    tests_passed,
                )

                # 评分
                score, details = score_scenario(scenario, output_files, metrics)
                if test_details:
                    details["test_commands"] = test_details

                # Save trace if requested.
                if self.save_traces:
                    trace_path = self.save_eval_trace(scenario, event_bus.events)
                    details["trace_path"] = str(trace_path)

                return ScenarioResult(
                    scenario_name=scenario.name,
                    success=score >= 0.8,  # 80% 以上算通过
                    score=score,
                    duration_sec=duration,
                    output_files=output_files,
                    details=details,
                    metrics=metrics,
                )
                
            except Exception as e:
                duration = time.time() - start_time
                return ScenarioResult(
                    scenario_name=scenario.name,
                    success=False,
                    score=0.0,
                    duration_sec=duration,
                    output_files={},
                    error=str(e),
                    metrics=EvalMetrics(duration_ms=int(duration * 1000)),
                )
    
    async def run_benchmark(self, scenarios: list[Scenario], model: str | None = None) -> BenchmarkReport:
        """运行基准测试"""
        start_time = time.time()
        
        # 如果指定了模型，覆盖所有场景的模型
        if model:
            for scenario in scenarios:
                scenario.model = model
        
        # 运行所有场景
        results = []
        for scenario in scenarios:
            print(f"Running scenario: {scenario.name}")
            result = await self.run_scenario(scenario)
            results.append(result)
            print(f"  Score: {result.score:.2f}, Success: {result.success}")
        
        # 生成报告
        total_duration = time.time() - start_time
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        average_score = sum(r.score for r in results) / len(results) if results else 0.0
        
        return BenchmarkReport(
            total_scenarios=len(scenarios),
            passed=passed,
            failed=failed,
            average_score=average_score,
            total_duration_sec=total_duration,
            results=results,
            model=model or scenarios[0].model if scenarios else "unknown",
            timestamp=datetime.now().isoformat(),
        )

    def save_eval_trace(self, scenario: Scenario, events: list[Event]) -> Path:
        """Persist a scenario trace under .agent/eval-traces by scenario name."""
        trace_dir = self.trace_dir or Path.cwd() / ".agent" / "eval-traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_path = trace_dir / f"{safe_trace_name(scenario.name)}.jsonl"

        with trace_path.open("w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

        return trace_path


def build_eval_extensions(scenario: Scenario, repo_root: str) -> list:
    """Create non-interactive safety extensions for eval scenarios."""
    policy = PolicyConfig(
        command=CommandPolicy(
            allow=[
                r"^pytest(\s|$)",
                r"^python\s+-m\s+pytest(\s|$)",
                r"^uv\s+run\s+pytest(\s|$)",
                r"^npm\s+test(\s|$)",
            ],
            confirm=[],
            deny=[],
        ),
        path=PathPolicy(
            deny=[
                ".env",
                "**/.env",
                "**/.ssh/**",
                "**/*.pem",
                "**/*.key",
                "**/*secret*",
            ],
            confirm_write=[
                "pyproject.toml",
                "package.json",
                "package-lock.json",
            ],
        ),
    )
    return [
        PolicyGateway(
            policy=policy,
            mode=ApprovalMode.WORKSPACE_WRITE,
            repo_root=repo_root,
            approval_handler=DenyApprovalHandler(),
        ),
        LoopGuardsExtension(
            options=LoopGuardOptions(
                goal=scenario.prompt,
                max_tool_calls=policy.limits.max_tool_calls,
                max_fix_iterations=policy.limits.max_fix_iterations,
                token_budget=policy.limits.token_budget,
            ),
        ),
    ]


def snapshot_workspace(root: Path) -> dict[str, str]:
    """Capture a text snapshot of files under ``root``."""
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        try:
            snapshot[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            snapshot[relative] = path.read_text(encoding="utf-8", errors="replace")
    return snapshot


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Return files whose content or existence changed."""
    changed = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            changed.append(path)
    return changed


def build_eval_metrics(
    scenario: Scenario,
    before_snapshot: dict[str, str],
    after_snapshot: dict[str, str],
    events: list[Event],
    duration_sec: float,
    tests_passed: bool | None,
) -> EvalMetrics:
    """Build structured eval metrics from snapshots and runtime events."""
    changed = changed_files(before_snapshot, after_snapshot)
    expected_paths = scenario.expected_changed_files or list(scenario.expected_files)

    expected_files_changed = bool(expected_paths) and all(
        path_matches_any(path, changed) for path in expected_paths
    )
    forbidden_files_touched = any(
        path_matches_any(path, changed) for path in scenario.forbidden_files
    )

    tool_calls = sum(1 for event in events if event.type == EventType.TOOL_CALL_REQUESTED)
    tokens = 0
    for event in events:
        if event.type != EventType.MODEL_RESPONSE:
            continue
        usage = event.payload.get("usage", {})
        tokens += int(usage.get("input_tokens", 0))
        tokens += int(usage.get("output_tokens", 0))

    dangerous_commands_blocked = any(
        event.type == EventType.POLICY_VERDICT
        and event.payload.get("verdict") == "deny"
        for event in events
    ) or any(
        event.type == EventType.TOOL_END
        and event.payload.get("is_error")
        and is_safety_error(str(event.payload.get("result", "")))
        for event in events
    )

    return EvalMetrics(
        tests_passed=tests_passed,
        expected_files_changed=expected_files_changed,
        forbidden_files_touched=forbidden_files_touched,
        dangerous_commands_blocked=dangerous_commands_blocked,
        tool_calls=tool_calls,
        tokens=tokens,
        duration_ms=int(duration_sec * 1000),
        changed_files=changed,
    )


def path_matches_any(pattern: str, paths: list[str]) -> bool:
    """Return whether a path pattern matches any path in ``paths``."""
    normalized = pattern.rstrip("/")
    for path in paths:
        if path == normalized:
            return True
        if fnmatch.fnmatch(path, pattern):
            return True
        if pattern.endswith("/") and path.startswith(pattern):
            return True
    return False


def is_safety_error(result: str) -> bool:
    """Best-effort detection of tool-level safety failures."""
    lowered = result.lower()
    return any(
        marker in lowered
        for marker in [
            "outside workspace",
            "outside repo",
            "path traversal",
            "symlink",
            "protected path",
            "tool blocked",
        ]
    )


def run_test_commands(
    root: Path,
    commands: list[str],
    timeout_sec: int,
) -> tuple[bool | None, list[dict]]:
    """Run trusted post-eval test commands and capture compact results."""
    if not commands:
        return None, []

    results = []
    passed = True
    for command in commands:
        try:
            completed = run(
                shlex.split(command),
                cwd=root,
                text=True,
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
            command_passed = completed.returncode == 0
            passed = passed and command_passed
            results.append(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout[-1000:],
                    "stderr": completed.stderr[-1000:],
                }
            )
        except (OSError, TimeoutExpired) as exc:
            passed = False
            results.append({"command": command, "error": str(exc)})

    return passed, results


def safe_trace_name(name: str) -> str:
    """Make a scenario name safe for filesystem trace filenames."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-")
    return safe or "scenario"
