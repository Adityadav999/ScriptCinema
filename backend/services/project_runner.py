"""
project_runner.py — Install dependencies and start the detected project server.
"""
import os
import subprocess
import sys
import time
from typing import Optional

import requests

from services.project_detector import ProjectConfig

IS_WINDOWS = sys.platform == "win32"


class ProjectRunner:
    """
    Manages the lifecycle of a cloned project:
      install() → start() → wait_for_ready() → stop()
    """

    def __init__(self, repo_dir: str, config: ProjectConfig):
        self.repo_dir = repo_dir
        self.config = config
        self._server: Optional[subprocess.Popen] = None

    # ── Install ───────────────────────────────────────────────────────────────
    def install(self, timeout: int = 300) -> None:
        """Run the install command synchronously (blocks until done)."""
        env = self._build_env()
        try:
            result = subprocess.run(
                self.config.install_cmd,
                cwd=self.repo_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=IS_WINDOWS,          # Required on Windows for .cmd wrappers
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Install command not found: {self.config.install_cmd[0]!r}. "
                f"Make sure the required runtime is installed and on PATH.\n({exc})"
            )

        if result.returncode != 0:
            out = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"Dependency installation failed for {self.config.project_type}:\n{out[:800]}"
            )

    # ── Start ─────────────────────────────────────────────────────────────────
    def start(self) -> None:
        """Start the project server as a background subprocess."""
        env = self._build_env()
        try:
            self._server = subprocess.Popen(
                self.config.start_cmd,
                cwd=self.repo_dir,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=IS_WINDOWS,          # Required on Windows for .cmd wrappers
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Start command not found: {self.config.start_cmd[0]!r}. "
                f"Make sure the required runtime is installed and on PATH.\n({exc})"
            )

    # ── Wait for ready ────────────────────────────────────────────────────────
    def wait_for_ready(self, timeout: int = 120) -> bool:
        """
        Poll http://localhost:<port> until it responds with a non-5xx status.
        Returns True if ready, False if timeout exceeded.
        """
        url = f"http://localhost:{self.config.port}"
        deadline = time.time() + timeout

        while time.time() < deadline:
            # Check process is still alive
            if self._server and self._server.poll() is not None:
                raise RuntimeError(
                    f"Server process exited unexpectedly (code {self._server.returncode}). "
                    f"The project may require environment variables or a database."
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

        return False

    # ── Stop ──────────────────────────────────────────────────────────────────
    def stop(self) -> None:
        """Terminate the server process gracefully, then forcefully if needed."""
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
        finally:
            # On Windows, shell=True spawns a cmd.exe parent; kill child processes too
            if IS_WINDOWS and self._server.pid:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self._server.pid)],
                        capture_output=True,
                    )
                except Exception:
                    pass
        self._server = None

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _build_env(self) -> dict:
        env = {**os.environ}
        env.update(self.config.env_vars)
        return env
