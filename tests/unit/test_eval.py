"""评测框架测试"""

import pytest

from codeagent.eval.loader import load_scenarios_from_yaml
from codeagent.eval.scoring import score_scenario
from codeagent.eval.types import Scenario


class TestScenarioLoader:
    """场景加载测试"""
    
    def test_load_simple_edit_scenarios(self):
        """测试加载简单编辑场景"""
        benchmarks_path = "src/codeagent/eval/benchmarks/simple_edit.yaml"
        scenarios = load_scenarios_from_yaml(benchmarks_path)
        
        assert len(scenarios) == 3
        assert scenarios[0].name == "fix-off-by-one"
        assert scenarios[1].name == "add-docstring"
        assert scenarios[2].name == "rename-variable"


class TestScoring:
    """评分测试"""
    
    def test_score_exact_match(self):
        """测试精确匹配评分"""
        scenario = Scenario(
            name="test",
            description="test",
            prompt="test",
            input_files={"main.py": "x = 1"},
            expected_files={"main.py": "x = 2"},
            scoring={"file_count": 1.0},
        )
        
        # 精确匹配
        output_files = {"main.py": "x = 2"}
        score, details = score_scenario(scenario, output_files)
        assert score == 1.0
    
    def test_score_partial_match(self):
        """测试部分匹配评分"""
        scenario = Scenario(
            name="test",
            description="test",
            prompt="test",
            input_files={"main.py": "x = 1"},
            expected_files={"main.py": "x = 2\ny = 3"},
            scoring={"file_count": 1.0},
        )
        
        # 部分匹配
        output_files = {"main.py": "x = 2"}
        score, details = score_scenario(scenario, output_files)
        assert 0.0 < score < 1.0  # 相似度评分
    
    def test_score_missing_file(self):
        """测试缺失文件评分"""
        scenario = Scenario(
            name="test",
            description="test",
            prompt="test",
            input_files={"main.py": "x = 1"},
            expected_files={"main.py": "x = 2", "other.py": "y = 3"},
            scoring={},
        )
        
        # 缺少一个文件
        output_files = {"main.py": "x = 2"}
        score, details = score_scenario(scenario, output_files)
        assert score < 1.0
