"""
project_runner.py — Install, start, and manage any detected project.
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
    def __init__(self, repo_dir: str, config: ProjectConfig):
        self.repo_dir = repo_dir
        self.config   = config
        self._server: Optional[subprocess.Popen] = None
        self._log_fh  = None
        self._log_path: Optional[str] = None

    # ── Install / Compile ─────────────────────────────────────────────────────
    def install(self, timeout: int = 300) -> None:
        """Run install_cmd (deps install OR compile step). Skipped if empty."""
        if not self.config.install_cmd:
            return   # nothing to install (e.g. bare Python scripts)

        env = self._build_env()
        cmd = _wrap(self.config.install_cmd)

        try:
            result = subprocess.run(
                cmd, cwd=self.repo_dir, env=env,
                capture_output=True, text=True, timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Install command not found: {cmd[0]!r}\n"
                f"Make sure the required runtime is installed and on PATH.\n{exc}"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Install/compile timed out after {timeout}s.")

        if result.returncode != 0:
            out = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"{self.config.project_type} install failed "
                f"(exit {result.returncode}):\n{out[:800]}"
            )

    # ── Start web server ──────────────────────────────────────────────────────
    def start(self) -> None:
        """Start the project web server as a background process."""
        env = self._build_env()
        cmd = _wrap(self.config.start_cmd)

        fd, self._log_path = tempfile.mkstemp(prefix="sc_server_", suffix=".log")
        self._log_fh = os.fdopen(fd, "w", encoding="utf-8", errors="replace")

        try:
            self._server = subprocess.Popen(
                cmd, cwd=self.repo_dir, env=env,
                stdout=self._log_fh, stderr=subprocess.STDOUT,
            )
        except FileNotFoundError as exc:
            self._log_fh.close()
            raise RuntimeError(
                f"Start command not found: {cmd[0]!r}\n"
                f"Make sure the required runtime is installed.\n{exc}"
            )

    # ── Wait for HTTP response ────────────────────────────────────────────────
    def wait_for_ready(self, timeout: int = 120) -> bool:
        """
        Poll http://localhost:<port> until ANY HTTP response is received.
        Accepts 4xx and 5xx — if the server replies at all, it's running.
        Only fails on ConnectionError (port not bound yet) or process death.
        """
        url      = f"http://localhost:{self.config.port}"
        deadline = time.time() + timeout

        while time.time() < deadline:
            if self._server and self._server.poll() is not None:
                log_snippet = self._read_log_tail(40)
                raise RuntimeError(
                    f"{self.config.project_type} server exited unexpectedly "
                    f"(code {self._server.returncode}).\n\n"
                    f"Server log:\n{log_snippet}"
                )
            try:
                requests.get(url, timeout=3, allow_redirects=True)
                # ✅ ANY response (200, 404, 500…) means the server is up
                return True
            except requests.exceptions.ConnectionError:
                pass   # port not bound yet — keep waiting
            except Exception:
                pass

            time.sleep(2)

        log_snippet = self._read_log_tail(30)
        raise RuntimeError(
            f"{self.config.project_type} server did not respond on "
            f"http://localhost:{self.config.port} within {timeout}s.\n\n"
            f"Server log:\n{log_snippet}\n\n"
            "The repo may require external services (DB, auth tokens) to start."
        )

    # ── Run non-web project and capture output ────────────────────────────────
    def run_and_capture(self, timeout: int = 30) -> list[str]:
        """
        For non-web projects: run start_cmd and return stdout+stderr as lines.
        Handles timeout gracefully — returns whatever was output so far.
        """
        env = self._build_env()
        cmd = _wrap(self.config.start_cmd)

        try:
            result = subprocess.run(
                cmd, cwd=self.repo_dir, env=env,
                capture_output=True, text=True,
                timeout=timeout, errors="replace",
            )
            combined = (result.stdout or "") + (result.stderr or "")
            lines    = combined.strip().splitlines()
            if not lines:
                code = result.returncode
                lines = [f"✓ Program finished (exit code {code})"]
            return lines

        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            lines = (stdout + stderr).strip().splitlines()
            if not lines:
                lines = [f"(Ran for {timeout}s — no output produced)"]
            lines.append(f"⏱  First {timeout}s of execution recorded")
            return lines

        except FileNotFoundError as exc:
            return [
                f"⚠  Runtime not found: {cmd[0]!r}",
                str(exc),
                "Install the required runtime and make sure it's on PATH.",
            ]

        except Exception as exc:
            return [f"⚠  Unexpected error: {exc}"]

    # ── Stop ──────────────────────────────────────────────────────────────────
    def stop(self) -> None:
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

        if IS_WINDOWS and self._server.pid:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._server.pid)],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass

        self._server = None
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
        if not self._log_path:
            return "(no log captured)"
        try:
            if self._log_fh and not self._log_fh.closed:
                self._log_fh.flush()
            content = Path(self._log_path).read_text(encoding="utf-8", errors="replace")
            tail    = content.strip().splitlines()[-lines:]
            return "\n".join(tail) if tail else "(log is empty)"
        except Exception as exc:
            return f"(could not read log: {exc})"
