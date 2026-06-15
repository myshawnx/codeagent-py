"""场景加载器"""

import yaml
from pathlib import Path

from .types import Scenario


def load_scenarios_from_yaml(yaml_path: str) -> list[Scenario]:
    """从 YAML 文件加载场景"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    scenarios = []
    for scenario_data in data.get("scenarios", []):
        scenario = Scenario(**scenario_data)
        scenarios.append(scenario)
    
    return scenarios


def load_all_benchmarks(benchmarks_dir: str) -> dict[str, list[Scenario]]:
    """加载所有基准测试"""
    benchmarks = {}
    benchmarks_path = Path(benchmarks_dir)
    
    for yaml_file in benchmarks_path.glob("*.yaml"):
        benchmark_name = yaml_file.stem
        scenarios = load_scenarios_from_yaml(str(yaml_file))
        benchmarks[benchmark_name] = scenarios
    
    return benchmarks
