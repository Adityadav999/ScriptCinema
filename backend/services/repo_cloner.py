"""
repo_cloner.py — Clone a GitHub repo to a temp directory.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path


def clone_repo(repo_url: str) -> str:
    """
    Clone a GitHub repository (shallow) to a fresh temp directory.
    Returns the absolute path to the cloned directory.
    """
    url = repo_url.strip().rstrip("/")
    if not url.endswith(".git"):
        url += ".git"

    tmp_dir = tempfile.mkdtemp(prefix="scriptcinema_")

    try:
        result = subprocess.run(
            ["git", "clone", "--depth=1", url, tmp_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ValueError(
                f"Git clone failed: {result.stderr.strip() or result.stdout.strip()}"
            )
        return tmp_dir

    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValueError("Git clone timed out after 120 seconds.")

    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def cleanup_repo(repo_dir: str) -> None:
    """Delete the cloned repo directory."""
    if repo_dir and Path(repo_dir).exists():
        shutil.rmtree(repo_dir, ignore_errors=True)
