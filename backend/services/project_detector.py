"""
project_detector.py — Inspect a cloned repo and determine how to run it.

Windows notes
-------------
* npm / npx ship as .cmd wrappers on Windows — always resolve with shutil.which().
* All commands here are lists; project_runner.py wraps them in ["cmd", "/c"] on Windows.
* Never use shell=True — it breaks quote handling for paths with spaces.
* Port is controlled via the PORT env var wherever possible (Next.js ≥12, CRA, Vite ≥5).
  For frameworks that ignore PORT, we pass an explicit --port flag.
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
    project_type: str
    install_cmd: list[str]
    start_cmd: list[str]
    port: int
    env_vars: dict[str, str] = field(default_factory=dict)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_free_port(start: int = 4000) -> int:
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


def _w(name: str) -> str:
    """
    Resolve an executable to its full path.
    On Windows try the .cmd variant first (npm.cmd, npx.cmd, …).
    Falls back to the bare name so subprocess gives a clear error.
    """
    if IS_WINDOWS:
        for variant in (name + ".cmd", name + ".CMD", name):
            found = shutil.which(variant)
            if found:
                return found
        return name + ".cmd"          # let subprocess surface the error clearly
    found = shutil.which(name)
    return found or name


def _python() -> str:
    """Absolute path to the current Python interpreter (always works in venv)."""
    return sys.executable


def _pip() -> list[str]:
    """pip invocation that works regardless of PATH — uses current interpreter."""
    return [_python(), "-m", "pip"]


# ── Detector ─────────────────────────────────────────────────────────────────

def detect_project(repo_dir: str) -> ProjectConfig:
    root = Path(repo_dir)
    port = _find_free_port()

    npm = _w("npm")
    npx = _w("npx")

    # ── 1. Node / JS / TS ────────────────────────────────────────────────────
    pkg_json = root / "package.json"
    if pkg_json.exists():
        pkg   = _read_json(pkg_json)
        deps  = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        scripts = pkg.get("scripts", {})

        # Next.js — PORT env var works on Next.js ≥12 (no need for --port flag)
        if "next" in deps:
            return ProjectConfig(
                project_type="Next.js",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npm, "run", "dev"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none"},
            )

        # Vite — supports --port flag AND VITE_PORT env (use flag, more reliable)
        if "vite" in deps or any(k.startswith("@vitejs/") for k in deps):
            return ProjectConfig(
                project_type="Vite",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                # Pass --port directly to vite via npx to avoid npm script arg quirks
                start_cmd=[npx, "vite", "--port", str(port), "--host"],
                port=port,
                env_vars={"BROWSER": "none"},
            )

        # Create React App — respects PORT env var
        if "react-scripts" in deps:
            return ProjectConfig(
                project_type="Create React App",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npm, "start"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none", "CI": "false"},
            )

        # Angular
        if "@angular/core" in deps:
            return ProjectConfig(
                project_type="Angular",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npx, "ng", "serve", "--port", str(port), "--host", "0.0.0.0"],
                port=port,
                env_vars={},
            )

        # Nuxt 3
        if "nuxt" in deps:
            return ProjectConfig(
                project_type="Nuxt",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npm, "run", "dev"],
                port=port,
                env_vars={"PORT": str(port), "NUXT_PORT": str(port), "BROWSER": "none"},
            )

        # Generic Node — dev script preferred over start
        if "dev" in scripts or "start" in scripts:
            cmd = [npm, "run", "dev"] if "dev" in scripts else [npm, "start"]
            return ProjectConfig(
                project_type="Node.js",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=cmd,
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none"},
            )

    # ── 2. Python ────────────────────────────────────────────────────────────
    has_req = (root / "requirements.txt").exists()
    has_pyp = (root / "pyproject.toml").exists()

    if has_req or has_pyp:
        req = _read_text(root / "requirements.txt") if has_req else ""

        # FastAPI / Uvicorn
        if ("fastapi" in req or "uvicorn" in req) and (root / "main.py").exists():
            return ProjectConfig(
                project_type="FastAPI",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[_python(), "-m", "uvicorn", "main:app",
                           "--host", "0.0.0.0", "--port", str(port)],
                port=port,
                env_vars={"PORT": str(port)},
            )

        # Flask
        flask_entry = next(
            (c for c in ["app.py", "wsgi.py", "run.py", "server.py", "application.py"]
             if (root / c).exists()),
            None,
        )
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
            )

        # Django
        if (root / "manage.py").exists():
            return ProjectConfig(
                project_type="Django",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[_python(), "manage.py", "runserver", f"0.0.0.0:{port}"],
                port=port,
                env_vars={"PORT": str(port)},
            )

        # Streamlit
        if "streamlit" in req:
            entry = next(
                (p.name for p in root.glob("*.py")
                 if "app" in p.name.lower() or "main" in p.name.lower()),
                "app.py",
            )
            return ProjectConfig(
                project_type="Streamlit",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[_python(), "-m", "streamlit", "run", entry,
                           "--server.port", str(port), "--server.headless", "true"],
                port=port,
                env_vars={"PORT": str(port)},
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
        )

    raise ValueError(
        "Could not detect the project type. "
        "Supported: Next.js, Vite, CRA, Angular, Nuxt, Node.js, "
        "FastAPI, Flask, Django, Streamlit, Go."
    )
