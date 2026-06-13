"""项目画像探测测试"""

import json
from pathlib import Path

import pytest

from codeagent.context.profile import detect_profile


@pytest.fixture
def node_project(temp_repo):
    """创建 Node.js 项目"""
    repo = Path(temp_repo)
    
    # package.json
    package_json = {
        "name": "test-project",
        "dependencies": {"react": "^18.0.0"},
        "devDependencies": {"typescript": "^5.0.0", "vitest": "^1.0.0"},
        "scripts": {"test": "vitest", "lint": "eslint .", "build": "tsc"},
    }
    (repo / "package.json").write_text(json.dumps(package_json))
    
    # tsconfig.json
    (repo / "tsconfig.json").write_text("{}")
    
    # pnpm-lock.yaml
    (repo / "pnpm-lock.yaml").write_text("lockfileVersion: '6.0'")
    
    # 目录
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    
    return temp_repo


@pytest.fixture
def python_project(temp_repo):
    """创建 Python 项目"""
    repo = Path(temp_repo)
    
    # pyproject.toml
    pyproject = """
[project]
name = "test-project"
version = "0.1.0"

[tool.uv]
dev-dependencies = ["pytest>=8.0.0"]
"""
    (repo / "pyproject.toml").write_text(pyproject)
    
    # uv.lock
    (repo / "uv.lock").touch()
    
    # 目录
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    
    return temp_repo


@pytest.fixture
def go_project(temp_repo):
    """创建 Go 项目"""
    repo = Path(temp_repo)
    
    # go.mod
    (repo / "go.mod").write_text("module example.com/test\n\ngo 1.21\n")
    
    # 目录
    (repo / "pkg").mkdir()
    (repo / "tests").mkdir()
    
    return temp_repo


class TestNodeDetection:
    """Node.js 项目检测测试"""
    
    def test_detect_typescript_project(self, node_project):
        """检测 TypeScript 项目"""
        profile = detect_profile(node_project)
        assert profile.language == "typescript"
        assert profile.package_manager == "pnpm"
        assert profile.framework == "react"
        assert profile.test_framework == "vitest"
        assert "src" in profile.source_dirs
        assert "tests" in profile.test_dirs
        assert profile.commands["test"] == "pnpm test"
        assert profile.commands["build"] == "pnpm run build"


class TestPythonDetection:
    """Python 项目检测测试"""
    
    def test_detect_python_project(self, python_project):
        """检测 Python 项目"""
        profile = detect_profile(python_project)
        assert profile.language == "python"
        assert profile.package_manager == "uv"
        assert profile.test_framework == "pytest"
        assert "src" in profile.source_dirs
        assert "tests" in profile.test_dirs
        assert profile.commands["test"] == "pytest"


class TestGoDetection:
    """Go 项目检测测试"""
    
    def test_detect_go_project(self, go_project):
        """检测 Go 项目"""
        profile = detect_profile(go_project)
        assert profile.language == "go"
        assert profile.package_manager == "go"
        assert "pkg" in profile.source_dirs
        assert "tests" in profile.test_dirs
        assert profile.commands["test"] == "go test ./..."


class TestUnknownProject:
    """未知项目测试"""
    
    def test_unknown_project_fallback(self, temp_repo):
        """未知项目类型回退"""
        repo = Path(temp_repo)
        (repo / "src").mkdir()
        
        profile = detect_profile(temp_repo)
        assert profile.language == "unknown"
        assert profile.package_manager == "unknown"
        assert "src" in profile.source_dirs
