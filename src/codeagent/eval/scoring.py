"""评分逻辑"""

import re
from difflib import SequenceMatcher

from .types import Scenario


def score_scenario(scenario: Scenario, output_files: dict[str, str]) -> tuple[float, dict]:
    """
    评分场景结果
    
    返回: (score, details)
    """
    details = {}
    scores = []
    
    # 1. 文件存在性检查
    for expected_path in scenario.expected_files.keys():
        if expected_path in output_files:
            details[f"file_exists_{expected_path}"] = True
            scores.append(1.0)
        else:
            details[f"file_exists_{expected_path}"] = False
            scores.append(0.0)
    
    # 2. 文件内容匹配
    for expected_path, expected_content in scenario.expected_files.items():
        if expected_path not in output_files:
            continue
        
        actual_content = output_files[expected_path]
        
        # 精确匹配
        if actual_content.strip() == expected_content.strip():
            details[f"exact_match_{expected_path}"] = True
            scores.append(1.0)
        else:
            # 相似度匹配
            similarity = SequenceMatcher(None, actual_content, expected_content).ratio()
            details[f"similarity_{expected_path}"] = similarity
            scores.append(similarity)
    
    # 3. 自定义评分规则
    for rule_name, rule_weight in scenario.scoring.items():
        if rule_name == "file_count":
            # 检查输出文件数量
            expected_count = len(scenario.expected_files)
            actual_count = len(output_files)
            if actual_count == expected_count:
                scores.append(rule_weight)
            else:
                scores.append(0.0)
    
    # 计算总分
    final_score = sum(scores) / len(scores) if scores else 0.0
    
    return final_score, details


def score_file_exact(expected: str, actual: str) -> float:
    """精确匹配评分"""
    return 1.0 if expected.strip() == actual.strip() else 0.0


def score_file_contains(expected: str, actual: str, substring: str) -> float:
    """包含检查评分"""
    return 1.0 if substring in actual else 0.0


def score_file_regex(expected: str, actual: str, pattern: str) -> float:
    """正则匹配评分"""
    return 1.0 if re.search(pattern, actual) else 0.0
