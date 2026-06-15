"""测试失败签名生成"""

import hashlib
import re


def create_failure_signature(result: dict) -> dict | None:
    """
    从工具结果创建失败签名
    
    用于检测重复的测试失败
    """
    content = result.get("content", [])
    is_error = result.get("is_error", False)
    
    if not is_error:
        return None
    
    # 提取文本内容
    text_content = _extract_text_content(content)
    
    # 提取失败的测试名称
    failing_tests = _extract_failing_tests(text_content)
    
    if not failing_tests:
        return None
    
    # 生成签名（基于测试名称，忽略具体错误信息）
    signature_input = "|".join(sorted(failing_tests))
    signature = hashlib.sha256(signature_input.encode()).hexdigest()[:16]
    
    return {
        "signature": signature,
        "failing_tests": failing_tests,
    }


def _extract_text_content(content: list) -> str:
    """从内容列表提取文本"""
    if isinstance(content, str):
        return content
    
    text_parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text_parts.append(item.get("text", ""))
        elif isinstance(item, str):
            text_parts.append(item)
    
    return "\n".join(text_parts)


def _extract_failing_tests(text: str) -> list[str]:
    """从输出中提取失败的测试名称"""
    failing_tests = []
    
    # Python pytest 格式
    pytest_pattern = r'FAILED\s+([\w/:.]+(?:::\w+)*)'
    failing_tests.extend(re.findall(pytest_pattern, text))
    
    # JavaScript jest/vitest 格式
    js_pattern = r'✕\s+(.*?)(?:\s+\(\d+\s*ms\))?$'
    failing_tests.extend(re.findall(js_pattern, text, re.MULTILINE))
    
    # Go 格式
    go_pattern = r'---\s*FAIL:\s*(\S+)'
    failing_tests.extend(re.findall(go_pattern, text))
    
    # 通用 FAIL 标记
    generic_pattern = r'FAIL:?\s+([\w.:/]+)'
    failing_tests.extend(re.findall(generic_pattern, text))
    
    return list(set(failing_tests))  # 去重
