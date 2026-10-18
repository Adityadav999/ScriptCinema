"""
repo_cloner.py — Clone a GitHub repo to a temp directory.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _git() -> str:
    """Return the git executable name (handles Windows PATH quirks)."""
    import shutil as _shutil
    found = _shutil.which("git")
    if found:
        return found
    # Common Windows install locations
    for candidate in [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
    ]:
        if Path(candidate).exists():
            return candidate
    return "git"


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
            [_git(), "clone", "--depth=1", url, tmp_dir],
            capture_output=True,
            text=True,
            timeout=120,
            # shell=True is NOT used here intentionally (security + cross-platform)
        )
        if result.returncode != 0:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ValueError(
                f"Git clone failed: {(result.stderr or result.stdout).strip()}"
            )
        return tmp_dir

    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValueError("Git clone timed out after 120 seconds.")

    except FileNotFoundError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValueError(
            "Git is not installed or not on PATH. "
            "Install Git from https://git-scm.com/download/win"
        )

    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def cleanup_repo(repo_dir: str) -> None:
    """Delete the cloned repo directory."""
    if repo_dir and Path(repo_dir).exists():
        shutil.rmtree(repo_dir, ignore_errors=True)
