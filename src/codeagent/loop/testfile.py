"""测试文件识别"""

import re
from pathlib import Path

from ..config.schema import ProjectProfile


def is_test_file(path: str, profile: ProjectProfile | None) -> bool:
    """
    检查文件是否是测试文件
    
    基于项目画像的测试目录和常见测试文件模式
    """
    if not profile:
        # 没有画像时使用通用规则
        return _is_test_file_generic(path)
    
    path_obj = Path(path)
    
    # 检查是否在测试目录中
    for test_dir in profile.test_dirs:
        try:
            path_obj.relative_to(test_dir)
            return True
        except ValueError:
            continue
    
    # 检查文件名模式
    return _is_test_file_generic(path)


def _is_test_file_generic(path: str) -> bool:
    """通用测试文件识别"""
    filename = Path(path).name.lower()
    
    # 常见测试文件模式
    test_patterns = [
        r'^test_.*\.py$',  # test_*.py
        r'.*_test\.py$',  # *_test.py
        r'^.*\.test\.(ts|js|tsx|jsx)$',  # *.test.ts/js
        r'^.*\.spec\.(ts|js|tsx|jsx)$',  # *.spec.ts/js
        r'^test.*\.go$',  # test*.go
        r'.*_test\.go$',  # *_test.go
    ]
    
    for pattern in test_patterns:
        if re.match(pattern, filename):
            return True
    
    return False


def is_test_fix_goal(goal: str) -> bool:
    """检查目标是否是修复测试"""
    keywords = ["fix test", "修复测试", "test fail", "测试失败", "failing test"]
    goal_lower = goal.lower()
    return any(keyword in goal_lower for keyword in keywords)


def allows_test_writes(goal: str) -> bool:
    """检查目标是否允许修改测试文件"""
    # 明确说明可以修改测试的情况
    allow_keywords = ["add test", "添加测试", "write test", "编写测试", "update test", "更新测试"]
    goal_lower = goal.lower()
    return any(keyword in goal_lower for keyword in allow_keywords)
