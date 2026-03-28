"""Shadow git checkpoint MCP server for Kiro CLI sessions."""

import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kiro-checkpoint")

SHADOW_DIR = ".kiro-shadow"


def _git(work_dir: str, *args: str) -> str:
    """Run git command against the shadow repo."""
    shadow = Path(work_dir) / SHADOW_DIR
    result = subprocess.run(
        ["git", f"--git-dir={shadow}", f"--work-tree={work_dir}", *args],
        capture_output=True,
        text=True,
        cwd=work_dir,
    )
    if result.returncode != 0 and result.stderr.strip():
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _ensure_init(work_dir: str) -> Path:
    shadow = Path(work_dir) / SHADOW_DIR
    if not shadow.exists():
        raise RuntimeError(f"No shadow repo in {work_dir}. Run init first.")
    return shadow


@mcp.tool()
def init(work_dir: str) -> str:
    """Initialize a shadow git repo for checkpointing in the given directory."""
    shadow = Path(work_dir) / SHADOW_DIR
    if shadow.exists():
        return f"Shadow repo already exists at {shadow}"
    subprocess.run(
        ["git", f"--git-dir={shadow}", f"--work-tree={work_dir}", "init"],
        capture_output=True,
        check=True,
    )
    # Exclude the shadow dir from tracking
    exclude = shadow / "info" / "exclude"
    exclude.write_text(f"{SHADOW_DIR}\n")
    _git(work_dir, "add", "-A")
    _git(work_dir, "commit", "-m", "initial checkpoint", "--allow-empty")
    return f"Shadow repo initialized at {shadow}"


@mcp.tool()
def checkpoint(work_dir: str, message: str) -> str:
    """Snapshot current state of all files with a message."""
    _ensure_init(work_dir)
    _git(work_dir, "add", "-A")
    if not _git(work_dir, "status", "--porcelain"):
        return "No changes to checkpoint."
    _git(work_dir, "commit", "-m", message)
    sha = _git(work_dir, "log", "-1", "--format=%h")
    return f"Checkpoint {sha}: {message}"


@mcp.tool()
def list_checkpoints(work_dir: str, branch: str = "", limit: int = 20) -> str:
    """List checkpoint history. Optionally filter by branch."""
    _ensure_init(work_dir)
    args = ["log", "--oneline", f"-{limit}"]
    if branch:
        args.append(branch)
    return _git(work_dir, *args) or "No checkpoints yet."


@mcp.tool()
def rollback(work_dir: str, ref: str) -> str:
    """Restore all files to a previous checkpoint (by short SHA or ref). Creates a new checkpoint recording the rollback."""
    _ensure_init(work_dir)
    _git(work_dir, "checkout", ref, "--", ".")
    _git(work_dir, "add", "-A")
    _git(work_dir, "commit", "-m", f"rollback to {ref}")
    return f"Rolled back to {ref}"


@mcp.tool()
def branch(work_dir: str, name: str, from_ref: str = "") -> str:
    """Create a new branch, optionally from a specific checkpoint."""
    _ensure_init(work_dir)
    args = ["checkout", "-b", name]
    if from_ref:
        args.append(from_ref)
    _git(work_dir, *args)
    return f"Created and switched to branch '{name}'"


@mcp.tool()
def list_branches(work_dir: str) -> str:
    """List all branches. Current branch is marked with *."""
    _ensure_init(work_dir)
    return _git(work_dir, "branch", "-v")


@mcp.tool()
def switch_branch(work_dir: str, name: str) -> str:
    """Switch to an existing branch, restoring its file state."""
    _ensure_init(work_dir)
    _git(work_dir, "checkout", name)
    return f"Switched to branch '{name}'"


@mcp.tool()
def diff(work_dir: str, ref: str = "") -> str:
    """Show changes since last checkpoint, or diff against a specific ref."""
    _ensure_init(work_dir)
    args = ["diff"]
    if ref:
        args.append(ref)
    result = _git(work_dir, *args)
    return result or "No changes."


def main():
    mcp.run()


if __name__ == "__main__":
    main()
