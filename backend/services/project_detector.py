"""
project_detector.py — Inspect a cloned repo and determine how to run it.
"""
import json
import shutil
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


@dataclass
class ProjectConfig:
    project_type: str           # Human-readable name, e.g. "Next.js"
    install_cmd: list[str]      # Command to install dependencies
    start_cmd: list[str]        # Command to start the dev server
    port: int                   # Port the server will listen on
    env_vars: dict[str, str] = field(default_factory=dict)
    use_shell: bool = False     # Whether subprocess should use shell=True


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_free_port(start: int = 4000) -> int:
    """Find an available TCP port starting from `start`."""
    for port in range(start, start + 200):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found in range 4000–4200.")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").lower()
    except Exception:
        return ""


def _exe(name: str) -> str:
    """
    Resolve an executable name to its full path (or .cmd on Windows).
    Falls back to the bare name if which() finds nothing — subprocess
    will raise FileNotFoundError with a clear message.
    """
    # On Windows npm/npx/node are shipped as .cmd wrappers
    if IS_WINDOWS and name in ("npm", "npx", "ng", "yarn", "pnpm"):
        cmd_name = name + ".cmd"
        found = shutil.which(cmd_name)
        if found:
            return found
        # Also try plain name (some installs add a .exe)
        found = shutil.which(name)
        if found:
            return found
        return cmd_name  # let subprocess surface the error

    found = shutil.which(name)
    return found if found else name


def _python() -> str:
    """Return path to the current Python interpreter."""
    return sys.executable


def _pip() -> list[str]:
    """Return a pip invocation using the current interpreter."""
    return [_python(), "-m", "pip"]


# ── Detector ─────────────────────────────────────────────────────────────────

def detect_project(repo_dir: str) -> ProjectConfig:
    """
    Inspect the repo directory and return a ProjectConfig describing
    how to install and start the project.
    """
    root = Path(repo_dir)
    port = _find_free_port()
    npm  = _exe("npm")
    npx  = _exe("npx")

    # ── 1. Node / JS / TS ────────────────────────────────────────────────────
    pkg_json = root / "package.json"
    if pkg_json.exists():
        pkg = _read_json(pkg_json)
        deps = {
            **pkg.get("dependencies", {}),
            **pkg.get("devDependencies", {}),
        }
        scripts = pkg.get("scripts", {})

        # Next.js
        if "next" in deps:
            return ProjectConfig(
                project_type="Next.js",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npm, "run", "dev", "--", f"--port={port}"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none"},
                use_shell=False,
            )

        # Vite (React / Vue / Svelte / Lit)
        if "vite" in deps or any(k.startswith("@vitejs/") for k in deps):
            return ProjectConfig(
                project_type="Vite",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npm, "run", "dev", "--", "--port", str(port), "--host"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none"},
                use_shell=False,
            )

        # Create React App
        if "react-scripts" in deps:
            return ProjectConfig(
                project_type="Create React App",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npm, "start"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none", "CI": "false"},
                use_shell=False,
            )

        # Angular
        if "@angular/core" in deps:
            return ProjectConfig(
                project_type="Angular",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npx, "ng", "serve", "--port", str(port), "--host", "0.0.0.0"],
                port=port,
                env_vars={},
                use_shell=False,
            )

        # Generic Node (express, fastify, etc.)
        if "dev" in scripts or "start" in scripts:
            cmd = [npm, "run", "dev"] if "dev" in scripts else [npm, "start"]
            return ProjectConfig(
                project_type="Node.js",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=cmd,
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none"},
                use_shell=False,
            )

    # ── 2. Python ────────────────────────────────────────────────────────────
    has_requirements = (root / "requirements.txt").exists()
    has_pyproject    = (root / "pyproject.toml").exists()

    if has_requirements or has_pyproject:
        req_text = _read_text(root / "requirements.txt") if has_requirements else ""

        # FastAPI / Uvicorn
        uvicorn = shutil.which("uvicorn") or "uvicorn"
        if ("fastapi" in req_text or "uvicorn" in req_text) and (root / "main.py").exists():
            return ProjectConfig(
                project_type="FastAPI",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[
                    _python(), "-m", "uvicorn", "main:app",
                    "--host", "0.0.0.0",
                    "--port", str(port),
                ],
                port=port,
                env_vars={"PORT": str(port)},
                use_shell=False,
            )

        # Flask
        flask_entry = None
        for candidate in ["app.py", "wsgi.py", "run.py", "server.py", "application.py"]:
            if (root / candidate).exists():
                flask_entry = candidate
                break

        if flask_entry:
            return ProjectConfig(
                project_type="Flask",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[_python(), flask_entry],
                port=port,
                env_vars={
                    "FLASK_APP": flask_entry,
                    "FLASK_ENV": "development",
                    "FLASK_RUN_PORT": str(port),
                    "PORT": str(port),
                },
                use_shell=False,
            )

        # Django
        if (root / "manage.py").exists():
            return ProjectConfig(
                project_type="Django",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[_python(), "manage.py", "runserver", f"0.0.0.0:{port}"],
                port=port,
                env_vars={"PORT": str(port)},
                use_shell=False,
            )

        # Streamlit
        if "streamlit" in req_text:
            entry = next(
                (str(p.name) for p in root.glob("*.py") if "app" in p.name.lower() or "main" in p.name.lower()),
                "app.py",
            )
            return ProjectConfig(
                project_type="Streamlit",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[
                    _python(), "-m", "streamlit", "run", entry,
                    "--server.port", str(port),
                    "--server.headless", "true",
                ],
                port=port,
                env_vars={"PORT": str(port)},
                use_shell=False,
            )

    # ── 3. Go ─────────────────────────────────────────────────────────────────
    if (root / "go.mod").exists():
        go = shutil.which("go") or "go"
        return ProjectConfig(
            project_type="Go",
            install_cmd=[go, "mod", "download"],
            start_cmd=[go, "run", "."],
            port=port,
            env_vars={"PORT": str(port)},
            use_shell=False,
        )

    raise ValueError(
        "Could not detect the project type. "
        "Supported stacks: Next.js, Vite, CRA, Angular, Node.js, "
        "FastAPI, Flask, Django, Streamlit, Go."
    )
