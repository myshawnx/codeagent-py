"""评测框架测试"""

import pytest

from oricode.eval.harness import EvalHarness, build_eval_metrics
from oricode.eval.loader import load_scenarios_from_yaml
from oricode.eval.scoring import score_scenario
from oricode.eval.types import EvalMetrics, Scenario
from oricode.runtime.events import Event, EventType


class TestScenarioLoader:
    """场景加载测试"""
    
    def test_load_simple_edit_scenarios(self):
        """测试加载简单编辑场景"""
        benchmarks_path = "src/oricode/eval/benchmarks/simple_edit.yaml"
        scenarios = load_scenarios_from_yaml(benchmarks_path)
        
        assert len(scenarios) == 3
        assert scenarios[0].name == "fix-off-by-one"
        assert scenarios[1].name == "add-docstring"
        assert scenarios[2].name == "rename-variable"

    @pytest.mark.parametrize(
        "benchmark",
        [
            "multi_file_refactor",
            "test_driven_fix",
            "instructions",
        ],
    )
    def test_load_richer_eval_benchmarks(self, benchmark):
        """测试加载更丰富的内置评测场景"""
        benchmarks_path = f"src/oricode/eval/benchmarks/{benchmark}.yaml"
        scenarios = load_scenarios_from_yaml(benchmarks_path)

        assert len(scenarios) >= 1
        assert scenarios[0].expected_changed_files
        assert isinstance(scenarios[0].forbidden_files, list)


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

    def test_score_metrics_rules(self):
        """测试结构化指标参与评分"""
        scenario = Scenario(
            name="test",
            description="test",
            prompt="test",
            expected_files={"main.py": "x = 2"},
            scoring={
                "file_exact": 1.0,
                "expected_files_changed": 1.0,
                "forbidden_files_clean": 1.0,
                "tests_passed": 1.0,
            },
        )
        metrics = EvalMetrics(
            tests_passed=True,
            expected_files_changed=True,
            forbidden_files_touched=False,
        )

        score, details = score_scenario(scenario, {"main.py": "x = 2"}, metrics)

        assert score == 1.0
        assert details["tests_passed"] is True

    def test_score_security_check_requires_block(self):
        """测试安全评分要求危险操作被阻断"""
        scenario = Scenario(
            name="security",
            description="test",
            prompt="test",
            scoring={"security_check": 1.0},
        )

        score, details = score_scenario(
            scenario,
            {},
            EvalMetrics(dangerous_commands_blocked=True),
        )

        assert score == 1.0
        assert details["security_check"] is True


class TestEvalMetrics:
    """评测指标测试"""

    def test_build_eval_metrics_from_snapshots_and_events(self):
        """测试从文件快照和事件构建指标"""
        scenario = Scenario(
            name="metrics",
            description="test",
            prompt="test",
            expected_changed_files=["main.py"],
            forbidden_files=["tests/**"],
        )
        before = {
            "main.py": "x = 1",
            "tests/test_main.py": "assert True",
        }
        after = {
            "main.py": "x = 2",
            "tests/test_main.py": "assert True",
        }
        events = [
            Event(EventType.TOOL_CALL_REQUESTED, session_id="s", payload={"tool": "write"}),
            Event(
                EventType.POLICY_VERDICT,
                session_id="s",
                payload={"verdict": "deny"},
            ),
            Event(
                EventType.MODEL_RESPONSE,
                session_id="s",
                payload={"usage": {"input_tokens": 5, "output_tokens": 7}},
            ),
        ]

        metrics = build_eval_metrics(
            scenario,
            before,
            after,
            events,
            duration_sec=0.25,
            tests_passed=True,
        )

        assert metrics.expected_files_changed is True
        assert metrics.forbidden_files_touched is False
        assert metrics.dangerous_commands_blocked is True
        assert metrics.tool_calls == 1
        assert metrics.tokens == 12
        assert metrics.duration_ms == 250

    def test_save_eval_trace_uses_scenario_name(self, tmp_path):
        """测试 eval trace 使用场景名保存"""
        scenario = Scenario(name="needs trace", description="test", prompt="test")
        harness = EvalHarness(save_traces=True, trace_dir=tmp_path)
        event = Event(EventType.SESSION_START, session_id="abc", payload={"ok": True})

        trace_path = harness.save_eval_trace(scenario, [event])

        assert trace_path == tmp_path / "needs-trace.jsonl"
        assert '"session_start"' in trace_path.read_text(encoding="utf-8")
