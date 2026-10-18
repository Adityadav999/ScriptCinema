"""
project_runner.py — Install dependencies and start the detected project server.

Windows notes
-------------
* On Windows, .cmd wrappers (npm.cmd, npx.cmd) require cmd.exe to execute.
  We wrap all commands with ["cmd", "/c"] instead of shell=True.
  shell=True with a list on Windows has subtle quoting bugs with space-containing paths.
* Server stdout/stderr is written to a log file so wait_for_ready() can surface
  the actual error when the process exits unexpectedly.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import requests

from services.project_detector import ProjectConfig

IS_WINDOWS = sys.platform == "win32"


def _wrap(cmd: list[str]) -> list[str]:
    """On Windows, prefix with cmd /c so .cmd wrappers execute correctly."""
    if IS_WINDOWS:
        return ["cmd", "/c"] + cmd
    return cmd


class ProjectRunner:
    """
    Manages the lifecycle of a cloned project:
      install() → start() → wait_for_ready() → stop()
    """

    def __init__(self, repo_dir: str, config: ProjectConfig):
        self.repo_dir = repo_dir
        self.config   = config
        self._server: Optional[subprocess.Popen]   = None
        self._log_fh  = None   # file handle for server output capture
        self._log_path: Optional[str] = None

    # ── Install ───────────────────────────────────────────────────────────────
    def install(self, timeout: int = 300) -> None:
        """Run the install command synchronously."""
        env = self._build_env()
        cmd = _wrap(self.config.install_cmd)

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Install command not found: {cmd[0]!r}. "
                f"Make sure the required runtime is installed.\n{exc}"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Dependency installation timed out after {timeout}s."
            )

        if result.returncode != 0:
            out = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"{self.config.project_type} install failed "
                f"(exit {result.returncode}):\n{out[:800]}"
            )

    # ── Start ─────────────────────────────────────────────────────────────────
    def start(self) -> None:
        """Start the project server as a background subprocess."""
        env  = self._build_env()
        cmd  = _wrap(self.config.start_cmd)

        # Capture server output to a temp file so we can read it on failure
        fd, self._log_path = tempfile.mkstemp(prefix="sc_server_", suffix=".log")
        self._log_fh = os.fdopen(fd, "w", encoding="utf-8", errors="replace")

        try:
            self._server = subprocess.Popen(
                cmd,
                cwd=self.repo_dir,
                env=env,
                stdout=self._log_fh,
                stderr=subprocess.STDOUT,   # merge stderr into same file
            )
        except FileNotFoundError as exc:
            self._log_fh.close()
            raise RuntimeError(
                f"Start command not found: {cmd[0]!r}. "
                f"Make sure the required runtime is installed.\n{exc}"
            )

    # ── Wait for ready ────────────────────────────────────────────────────────
    def wait_for_ready(self, timeout: int = 120) -> bool:
        """
        Poll http://localhost:<port> until it responds (non-5xx).
        Returns True if ready within timeout.
        Raises RuntimeError with server log excerpt if process dies early.
        """
        url      = f"http://localhost:{self.config.port}"
        deadline = time.time() + timeout

        while time.time() < deadline:
            # Check the process hasn't crashed
            if self._server and self._server.poll() is not None:
                log_snippet = self._read_log_tail(40)
                raise RuntimeError(
                    f"{self.config.project_type} server exited unexpectedly "
                    f"(code {self._server.returncode}).\n\n"
                    f"Server output:\n{log_snippet}"
                )

            try:
                resp = requests.get(url, timeout=3, allow_redirects=True)
                if resp.status_code < 500:
                    return True
            except requests.exceptions.ConnectionError:
                pass
            except Exception:
                pass

            time.sleep(2)

        # Timeout — attach last server log lines to the error
        log_snippet = self._read_log_tail(30)
        raise RuntimeError(
            f"{self.config.project_type} server did not respond on "
            f"http://localhost:{self.config.port} within {timeout}s.\n\n"
            f"Server output (last lines):\n{log_snippet}\n\n"
            f"Make sure the repo starts a web server and doesn't require "
            f"environment variables, a database, or auth tokens."
        )

    # ── Stop ──────────────────────────────────────────────────────────────────
    def stop(self) -> None:
        """Terminate the server process gracefully, then forcefully."""
        if self._log_fh:
            try:
                self._log_fh.close()
            except Exception:
                pass
            self._log_fh = None

        if not self._server:
            return

        try:
            self._server.terminate()
            self._server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                self._server.kill()
            except Exception:
                pass
        except Exception:
            pass

        # On Windows, kill child process tree (cmd /c spawns children)
        if IS_WINDOWS and self._server.pid:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._server.pid)],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass

        self._server = None

        # Clean up log file
        if self._log_path and Path(self._log_path).exists():
            try:
                Path(self._log_path).unlink()
            except Exception:
                pass
            self._log_path = None

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _build_env(self) -> dict:
        env = {**os.environ}
        env.update(self.config.env_vars)
        return env

    def _read_log_tail(self, lines: int = 30) -> str:
        """Read the last N lines from the server log file."""
        if not self._log_path:
            return "(no log captured)"
        try:
            # Flush what's buffered
            if self._log_fh and not self._log_fh.closed:
                self._log_fh.flush()
            content = Path(self._log_path).read_text(encoding="utf-8", errors="replace")
            tail    = content.strip().splitlines()[-lines:]
            return "\n".join(tail) if tail else "(log is empty)"
        except Exception as exc:
            return f"(could not read log: {exc})"
