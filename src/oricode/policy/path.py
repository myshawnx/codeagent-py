"""路径保护逻辑"""

from pathlib import Path, PurePath

from ..config.schema import PathPolicy


def path_matches_patterns(path: str, patterns: list[str]) -> bool:
    """检查路径是否匹配任一模式（支持 glob，包括 ** 递归匹配）"""
    pure_path = PurePath(path)
    for pattern in patterns:
        # PurePath.match() supports **, but **/*.ext only matches nested paths.
        # Try both the pattern and a root-level fallback (strip leading **/).
        if pure_path.match(pattern):
            return True
        # If pattern starts with **/, also try without it to match root-level files.
        if pattern.startswith("**/") and pure_path.match(pattern[3:]):
            return True
    return False


def path_denied(path: str, policy: PathPolicy) -> bool:
    """检查路径是否被拒绝访问"""
    return path_matches_patterns(path, policy.deny)


def path_confirm_write(path: str, policy: PathPolicy) -> bool:
    """检查路径写入是否需要确认"""
    return path_matches_patterns(path, policy.confirm_write)


def outside_repo_root(path: str, repo_root: str) -> bool:
    """检查路径是否在仓库根目录外"""
    # 相对路径默认认为在仓库内
    if not Path(path).is_absolute():
        return False

    try:
        path_obj = Path(path).resolve()
        repo_obj = Path(repo_root).resolve()

        # 检查 path 是否是 repo_root 的子路径
        try:
            path_obj.relative_to(repo_obj)
            return False
        except ValueError:
            return True
    except (ValueError, OSError):
        # 路径无效时保守处理，相对路径认为在内
        return False


def target_path(input_dict: dict) -> str | None:
    """从工具输入中提取目标路径"""
    # write/edit/read 工具
    if "file_path" in input_dict:
        return input_dict["file_path"]
    
    # grep/find 工具
    if "path" in input_dict:
        return input_dict["path"]
    
    # apply_patch 工具
    if "target" in input_dict:
        return input_dict["target"]
    
    return None


def bash_touches_protected_path(command: str, policy: PathPolicy) -> bool:
    """
    检查 bash 命令是否可能写入受保护路径
    
    这是字符串级别的 best-effort 检测，不是完整的 shell 解析
    """
    # 检查重定向操作符
    if ">" in command or ">>" in command or "tee" in command:
        # 简单检测：提取重定向目标
        for protected in policy.deny + policy.confirm_write:
            # 去掉 glob 通配符做简单字符串匹配
            base_pattern = protected.replace("*", "").replace("?", "")
            if base_pattern and base_pattern in command:
                return True
    
    return False
