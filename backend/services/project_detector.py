"""
project_detector.py — Inspect a cloned repo and determine how to run it.
"""
import json
import socket
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectConfig:
    project_type: str          # Human-readable name, e.g. "Next.js"
    install_cmd: list[str]     # Command to install dependencies
    start_cmd: list[str]       # Command to start the dev server
    port: int                  # Port the server will listen on
    env_vars: dict[str, str] = field(default_factory=dict)  # Extra env vars


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
    raise RuntimeError("No free port found in range 4000-4200.")


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


# ── Detector ─────────────────────────────────────────────────────────────────

def detect_project(repo_dir: str) -> ProjectConfig:
    """
    Inspect the repo directory and return a ProjectConfig describing
    how to install and start the project.

    Detection order (first match wins):
      1. Node.js projects via package.json (Next.js → Vite → CRA → generic)
      2. Python projects via requirements.txt / pyproject.toml
         (FastAPI/Uvicorn → Flask → Django)
    """
    root = Path(repo_dir)
    port = _find_free_port()

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
                install_cmd=["npm", "install", "--legacy-peer-deps"],
                start_cmd=["npm", "run", "dev", "--", f"--port={port}"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none"},
            )

        # Vite (React / Vue / Svelte)
        if "vite" in deps or "@vitejs/plugin-react" in deps:
            return ProjectConfig(
                project_type="Vite",
                install_cmd=["npm", "install", "--legacy-peer-deps"],
                start_cmd=["npm", "run", "dev", "--", "--port", str(port), "--host"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none"},
            )

        # Create React App
        if "react-scripts" in deps:
            return ProjectConfig(
                project_type="Create React App",
                install_cmd=["npm", "install", "--legacy-peer-deps"],
                start_cmd=["npm", "start"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none", "CI": "false"},
            )

        # Angular
        if "@angular/core" in deps:
            return ProjectConfig(
                project_type="Angular",
                install_cmd=["npm", "install", "--legacy-peer-deps"],
                start_cmd=["npx", "ng", "serve", "--port", str(port), "--host", "0.0.0.0"],
                port=port,
                env_vars={},
            )

        # Generic Node (Express, Fastify, etc.)
        if "start" in scripts or "dev" in scripts:
            cmd = ["npm", "run", "dev"] if "dev" in scripts else ["npm", "start"]
            return ProjectConfig(
                project_type="Node.js",
                install_cmd=["npm", "install", "--legacy-peer-deps"],
                start_cmd=cmd,
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none"},
            )

    # ── 2. Python ────────────────────────────────────────────────────────────
    has_requirements = (root / "requirements.txt").exists()
    has_pyproject = (root / "pyproject.toml").exists()

    if has_requirements or has_pyproject:
        req_text = _read_text(root / "requirements.txt") if has_requirements else ""

        # FastAPI / Uvicorn
        if ("fastapi" in req_text or "uvicorn" in req_text) and (root / "main.py").exists():
            return ProjectConfig(
                project_type="FastAPI",
                install_cmd=["pip", "install", "-r", "requirements.txt"],
                start_cmd=[
                    "uvicorn", "main:app",
                    "--host", "0.0.0.0",
                    "--port", str(port),
                    "--reload",
                ],
                port=port,
                env_vars={"PORT": str(port)},
            )

        # Flask — common entry points
        flask_entry = None
        for candidate in ["app.py", "wsgi.py", "run.py", "server.py", "application.py"]:
            if (root / candidate).exists():
                flask_entry = candidate
                break

        if flask_entry and ("flask" in req_text or "flask" in _read_text(root / flask_entry)):
            return ProjectConfig(
                project_type="Flask",
                install_cmd=["pip", "install", "-r", "requirements.txt"],
                start_cmd=["python", flask_entry],
                port=port,
                env_vars={
                    "FLASK_APP": flask_entry,
                    "FLASK_ENV": "development",
                    "FLASK_RUN_PORT": str(port),
                    "PORT": str(port),
                },
            )

        # Django
        if (root / "manage.py").exists():
            return ProjectConfig(
                project_type="Django",
                install_cmd=["pip", "install", "-r", "requirements.txt"],
                start_cmd=["python", "manage.py", "runserver", f"0.0.0.0:{port}"],
                port=port,
                env_vars={"PORT": str(port)},
            )

        # Streamlit
        if "streamlit" in req_text:
            entry = next(
                (str(p) for p in root.rglob("*.py") if "app" in p.name.lower() or "main" in p.name.lower()),
                "app.py",
            )
            return ProjectConfig(
                project_type="Streamlit",
                install_cmd=["pip", "install", "-r", "requirements.txt"],
                start_cmd=[
                    "streamlit", "run", entry,
                    "--server.port", str(port),
                    "--server.headless", "true",
                ],
                port=port,
                env_vars={"PORT": str(port)},
            )

    # ── 3. Go ─────────────────────────────────────────────────────────────────
    if (root / "go.mod").exists():
        return ProjectConfig(
            project_type="Go",
            install_cmd=["go", "mod", "download"],
            start_cmd=["go", "run", "."],
            port=port,
            env_vars={"PORT": str(port)},
        )

    raise ValueError(
        "Could not detect the project type. "
        "Supported stacks: Next.js, Vite, CRA, Angular, Node.js, "
        "FastAPI, Flask, Django, Streamlit, Go."
    )
