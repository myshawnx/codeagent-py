"""评测运行器 - 确定性、离线评测"""

import asyncio
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

from ..runtime.session import AgentSession
from .scoring import score_scenario
from .types import Scenario, ScenarioResult, BenchmarkReport


class EvalHarness:
    """评测运行器"""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
    
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
                
                # 创建 Agent 会话
                session = AgentSession(
                    cwd=tmpdir,
                    api_key=self.api_key,
                    model=scenario.model,
                )
                
                # 运行 Agent
                try:
                    await asyncio.wait_for(
                        session.run(scenario.prompt),
                        timeout=scenario.timeout_sec,
                    )
                except asyncio.TimeoutError:
                    return ScenarioResult(
                        scenario_name=scenario.name,
                        success=False,
                        score=0.0,
                        duration_sec=time.time() - start_time,
                        output_files={},
                        error=f"Timeout after {scenario.timeout_sec}s",
                    )
                
                # 收集输出文件
                output_files = {}
                for expected_path in scenario.expected_files.keys():
                    file_path = Path(tmpdir) / expected_path
                    if file_path.exists():
                        output_files[expected_path] = file_path.read_text(encoding="utf-8")
                
                # 评分
                score, details = score_scenario(scenario, output_files)
                
                duration = time.time() - start_time
                
                return ScenarioResult(
                    scenario_name=scenario.name,
                    success=score >= 0.8,  # 80% 以上算通过
                    score=score,
                    duration_sec=duration,
                    output_files=output_files,
                    details=details,
                )
                
            except Exception as e:
                return ScenarioResult(
                    scenario_name=scenario.name,
                    success=False,
                    score=0.0,
                    duration_sec=time.time() - start_time,
                    output_files={},
                    error=str(e),
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
