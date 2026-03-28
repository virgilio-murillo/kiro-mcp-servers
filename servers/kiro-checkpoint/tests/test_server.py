"""Tests for kiro-checkpoint MCP server."""
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def work_dir(tmp_path):
    return str(tmp_path)


def test_module_imports():
    from server import mcp, main, init, checkpoint, diff
    assert mcp is not None


def test_init_creates_shadow(work_dir):
    from server import init
    result = init(work_dir)
    assert "initialized" in result
    assert (Path(work_dir) / ".kiro-shadow").exists()


def test_init_idempotent(work_dir):
    from server import init
    init(work_dir)
    result = init(work_dir)
    assert "already exists" in result


def test_checkpoint_and_list(work_dir):
    from server import init, checkpoint, list_checkpoints
    init(work_dir)
    (Path(work_dir) / "test.txt").write_text("hello")
    result = checkpoint(work_dir, "add test file")
    assert "Checkpoint" in result
    log = list_checkpoints(work_dir)
    assert "add test file" in log


def test_no_changes(work_dir):
    from server import init, checkpoint
    init(work_dir)
    result = checkpoint(work_dir, "empty")
    assert "No changes" in result


def test_diff_no_changes(work_dir):
    from server import init, diff
    init(work_dir)
    result = diff(work_dir)
    assert "No changes" in result


def test_branch_and_switch(work_dir):
    from server import init, branch, list_branches, switch_branch
    init(work_dir)
    branch(work_dir, "feature")
    branches = list_branches(work_dir)
    assert "feature" in branches
    switch_branch(work_dir, "main")
    branches = list_branches(work_dir)
    assert "* main" in branches
