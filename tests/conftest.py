"""Pytest 配置和共享 fixtures"""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_repo(temp_dir):
    """创建临时仓库目录"""
    repo = Path(temp_dir) / "repo"
    repo.mkdir()
    return str(repo)
