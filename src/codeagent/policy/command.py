"""Bash 命令分类器"""

import re

from ..config.schema import CommandPolicy


def classify_command(command: str, policy: CommandPolicy) -> str:
    """
    分类 bash 命令
    
    返回: "allow" | "confirm" | "deny"
    """
    # 先检查 deny 规则
    for pattern in policy.deny:
        if re.search(pattern, command, re.IGNORECASE):
            return "deny"
    
    # 检查 confirm 规则
    for pattern in policy.confirm:
        if re.search(pattern, command, re.IGNORECASE):
            return "confirm"
    
    # 检查 allow 规则
    for pattern in policy.allow:
        if re.search(pattern, command, re.IGNORECASE):
            return "allow"
    
    # 内置的危险命令检测
    dangerous_patterns = [
        r'\brm\s+-rf\b',  # rm -rf
        r'\bcurl\s+.*\|\s*sh\b',  # curl | sh
        r'\bcurl\s+.*\|\s*bash\b',  # curl | bash
        r'\bwget\s+.*\|\s*sh\b',  # wget | sh
        r'>\s*/dev/sd[a-z]',  # 写入磁盘设备
        r'\bdd\s+.*of=/dev/',  # dd 写入设备
        r'\bmkfs\b',  # 格式化文件系统
        r'\bchmod\s+777\b',  # 过于宽松的权限
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return "deny"
    
    # 默认需要确认（保守策略）
    return "confirm"
