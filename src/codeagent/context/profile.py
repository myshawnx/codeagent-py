"""项目画像探测"""

import json
from pathlib import Path

from ..config.schema import ProjectProfile


def detect_profile(cwd: str) -> ProjectProfile:
    """
    探测项目画像
    
    返回项目的语言、包管理器、框架等信息
    """
    cwd_path = Path(cwd)
    
    # 尝试各种语言检测
    profile = (
        _detect_node(cwd_path)
        or _detect_python(cwd_path)
        or _detect_go(cwd_path)
        or _unknown_profile(cwd_path)
    )
    
    return profile


def _detect_node(cwd: Path) -> ProjectProfile | None:
    """检测 Node.js 项目"""
    package_json = cwd / "package.json"
    if not package_json.exists():
        return None
    
    try:
        with open(package_json, encoding="utf-8") as f:
            pkg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    scripts = pkg.get("scripts", {})
    
    # 检测包管理器
    pm = "npm"
    if (cwd / "pnpm-lock.yaml").exists():
        pm = "pnpm"
    elif (cwd / "yarn.lock").exists():
        pm = "yarn"
    elif (cwd / "bun.lockb").exists() or (cwd / "bun.lock").exists():
        pm = "bun"
    
    # 检测语言
    is_ts = (cwd / "tsconfig.json").exists() or "typescript" in deps
    language = "typescript" if is_ts else "javascript"
    
    # 检测框架
    framework = _detect_js_framework(deps)
    test_framework = _detect_js_test_framework(deps)
    
    # 检测目录
    source_dirs = _find_dirs(cwd, ["src", "lib", "app"])
    test_dirs = _find_dirs(cwd, ["test", "tests", "__tests__", "spec"])
    
    # 检测命令
    commands = {}
    if "test" in scripts:
        commands["test"] = f"{pm} test"
    if "lint" in scripts:
        commands["lint"] = f"{pm} run lint"
    if "build" in scripts:
        commands["build"] = f"{pm} run build"
    
    return ProjectProfile(
        language=language,
        package_manager=pm,
        framework=framework,
        test_framework=test_framework,
        source_dirs=source_dirs,
        test_dirs=test_dirs,
        commands=commands,
    )


def _detect_python(cwd: Path) -> ProjectProfile | None:
    """检测 Python 项目"""
    pyproject = cwd / "pyproject.toml"
    setup_py = cwd / "setup.py"
    requirements = cwd / "requirements.txt"
    
    has_python = pyproject.exists() or setup_py.exists() or requirements.exists()
    if not has_python:
        return None
    
    # 检测包管理器
    pm = "pip"
    pyproject_text = ""
    if pyproject.exists():
        pyproject_text = pyproject.read_text(encoding="utf-8")
        
        if (cwd / "poetry.lock").exists() or "[tool.poetry]" in pyproject_text:
            pm = "poetry"
        elif (cwd / "pdm.lock").exists() or "[tool.pdm]" in pyproject_text:
            pm = "pdm"
        elif (cwd / "uv.lock").exists() or "[tool.uv]" in pyproject_text:
            pm = "uv"
    
    if (cwd / "Pipfile").exists():
        pm = "pipenv"
    
    # 检测测试框架
    test_framework = None
    all_text = pyproject_text
    if requirements.exists():
        all_text += "\n" + requirements.read_text(encoding="utf-8")
    
    if "pytest" in all_text:
        test_framework = "pytest"
    
    # 检测目录
    source_dirs = _find_dirs(cwd, ["src", "lib"])
    test_dirs = _find_dirs(cwd, ["test", "tests"])
    
    # 检测命令
    commands = {}
    if test_framework:
        commands["test"] = "pytest"
    
    return ProjectProfile(
        language="python",
        package_manager=pm,
        test_framework=test_framework,
        source_dirs=source_dirs,
        test_dirs=test_dirs,
        commands=commands,
    )


def _detect_go(cwd: Path) -> ProjectProfile | None:
    """检测 Go 项目"""
    go_mod = cwd / "go.mod"
    if not go_mod.exists():
        return None
    
    source_dirs = _find_dirs(cwd, ["pkg", "internal", "cmd"])
    test_dirs = _find_dirs(cwd, ["test", "tests"])
    
    return ProjectProfile(
        language="go",
        package_manager="go",
        source_dirs=source_dirs,
        test_dirs=test_dirs,
        commands={
            "test": "go test ./...",
            "build": "go build ./...",
        },
    )


def _unknown_profile(cwd: Path) -> ProjectProfile:
    """未知项目类型的默认画像"""
    source_dirs = _find_dirs(cwd, ["src", "lib"])
    test_dirs = _find_dirs(cwd, ["test", "tests"])
    
    return ProjectProfile(
        language="unknown",
        package_manager="unknown",
        source_dirs=source_dirs,
        test_dirs=test_dirs,
        commands={},
    )


def _detect_js_framework(deps: dict) -> str | None:
    """检测 JavaScript 框架"""
    frameworks = [
        ("next", "next"),
        ("nuxt", "nuxt"),
        ("@sveltejs/kit", "sveltekit"),
        ("@nestjs/core", "nestjs"),
        ("@angular/core", "angular"),
        ("remix", "remix"),
        ("hono", "hono"),
        ("express", "express"),
        ("fastify", "fastify"),
        ("koa", "koa"),
        ("react", "react"),
        ("vue", "vue"),
        ("svelte", "svelte"),
    ]
    
    for dep, name in frameworks:
        if dep in deps:
            return name
    
    return None


def _detect_js_test_framework(deps: dict) -> str | None:
    """检测 JavaScript 测试框架"""
    frameworks = [
        ("vitest", "vitest"),
        ("jest", "jest"),
        ("mocha", "mocha"),
        ("ava", "ava"),
        ("@playwright/test", "playwright"),
        ("jasmine", "jasmine"),
    ]
    
    for dep, name in frameworks:
        if dep in deps:
            return name
    
    return None


def _find_dirs(cwd: Path, candidates: list[str]) -> list[str]:
    """查找存在的目录"""
    found = []
    for candidate in candidates:
        dir_path = cwd / candidate
        if dir_path.exists() and dir_path.is_dir():
            found.append(candidate)
    return found
