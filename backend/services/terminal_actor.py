"""
terminal_actor.py — Run a non-web project and capture its output for cinema rendering.
"""
import os
import subprocess
import sys
from typing import Optional, Callable

IS_WINDOWS = sys.platform == "win32"


def run_and_capture(
    cmd: list[str],
    repo_dir: str,
    env: dict,
    timeout: int = 30,
    on_progress: Optional[Callable[[str], None]] = None,
) -> list[str]:
    """
    Execute the program, capture stdout+stderr, return as a list of lines.
    Handles timeout gracefully — returns whatever was output so far.
    """
    def _p(msg):
        if on_progress:
            on_progress(msg)

    full_cmd = (["cmd", "/c"] + cmd) if IS_WINDOWS else cmd

    _p(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            full_cmd,
            cwd=repo_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        combined = (result.stdout or "") + (result.stderr or "")
        lines = combined.strip().splitlines()
        if not lines:
            exit_msg = "✓ Program completed" if result.returncode == 0 else f"⚠ Exited with code {result.returncode}"
            lines = [exit_msg]
        _p(f"Captured {len(lines)} lines of output")
        return lines

    except subprocess.TimeoutExpired as exc:
        # Use whatever partial output was captured
        stdout = (exc.stdout or b"")
        stderr = (exc.stderr or b"")
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        combined = stdout + stderr
        lines = combined.strip().splitlines()
        if not lines:
            lines = [f"(Program ran for {timeout}s — no output captured)"]
        lines.append(f"⏱ Recorded first {timeout}s of execution")
        _p(f"Timeout — captured {len(lines)} lines")
        return lines

    except FileNotFoundError as exc:
        return [f"Error: could not run {cmd[0]!r}", str(exc),
                "Make sure the required runtime (Python/Java/GCC/Node) is installed."]

    except Exception as exc:
        return [f"Unexpected error: {exc}"]
