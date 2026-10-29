"""
project_detector.py — Inspect a cloned repo and determine how to run it.

Supports web projects (browser-recorded) and non-web projects (terminal-recorded):
  Web:     Next.js, Vite, CRA, Angular, Nuxt, Node.js, FastAPI, Flask, Django, Streamlit, Go web
  Non-web: Python scripts, C, C++, Java, Maven, Gradle, Node CLI, Ruby, Rust
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
    install_cmd: list[str]   # deps install / compile step (may be empty [])
    start_cmd: list[str]     # web: server start  |  non-web: program run cmd
    port: int                # 0 for non-web projects
    env_vars: dict[str, str] = field(default_factory=dict)
    is_web: bool = True      # False → use terminal_actor instead of browser_actor


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
    """Resolve executable, using .cmd variant on Windows for Node tools."""
    if IS_WINDOWS:
        for variant in (name + ".cmd", name + ".CMD", name):
            found = shutil.which(variant)
            if found:
                return found
        return name + ".cmd"
    return shutil.which(name) or name


def _python() -> str:
    return sys.executable


def _pip() -> list[str]:
    return [_python(), "-m", "pip"]


def _has(root: Path, *names: str) -> bool:
    return any((root / n).exists() for n in names)


def _find_files(root: Path, ext: str, limit: int = 5) -> list[Path]:
    return list(root.rglob(f"*.{ext}"))[:limit]


# ── Detector ─────────────────────────────────────────────────────────────────

def detect_project(repo_dir: str) -> ProjectConfig:
    root = Path(repo_dir)
    port = _find_free_port()
    npm  = _w("npm")
    npx  = _w("npx")

    # ═══════════════════════════════════════════════════════════════════════
    # 1. NODE / JAVASCRIPT / TYPESCRIPT  (web)
    # ═══════════════════════════════════════════════════════════════════════
    pkg_json = root / "package.json"
    if pkg_json.exists():
        pkg     = _read_json(pkg_json)
        deps    = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        scripts = pkg.get("scripts", {})

        # Next.js
        if "next" in deps:
            return ProjectConfig(
                project_type="Next.js",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npm, "run", "dev"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none"},
                is_web=True,
            )

        # Vite (React / Vue / Svelte / Lit)
        if "vite" in deps or any(k.startswith("@vitejs/") for k in deps):
            return ProjectConfig(
                project_type="Vite",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npx, "vite", "--port", str(port), "--host"],
                port=port,
                env_vars={"BROWSER": "none"},
                is_web=True,
            )

        # Create React App
        if "react-scripts" in deps:
            return ProjectConfig(
                project_type="Create React App",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npm, "start"],
                port=port,
                env_vars={"PORT": str(port), "BROWSER": "none", "CI": "false"},
                is_web=True,
            )

        # Angular
        if "@angular/core" in deps:
            return ProjectConfig(
                project_type="Angular",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npx, "ng", "serve", "--port", str(port), "--host", "0.0.0.0"],
                port=port,
                env_vars={},
                is_web=True,
            )

        # Nuxt 3
        if "nuxt" in deps:
            return ProjectConfig(
                project_type="Nuxt",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[npm, "run", "dev"],
                port=port,
                env_vars={"PORT": str(port), "NUXT_PORT": str(port), "BROWSER": "none"},
                is_web=True,
            )

        # Generic Node web server (express, fastify, koa…)
        if "express" in deps or "fastify" in deps or "koa" in deps or "hapi" in deps:
            cmd = [npm, "run", "dev"] if "dev" in scripts else [npm, "start"]
            return ProjectConfig(
                project_type="Node.js (Express/Fastify)",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=cmd,
                port=port,
                env_vars={"PORT": str(port)},
                is_web=True,
            )

        # Node.js CLI / script (has package.json but no web server)
        node = shutil.which("node") or "node"
        entry = next(
            (pkg.get("main") or pkg.get("bin") or None), None
        )
        if isinstance(entry, dict):
            entry = next(iter(entry.values()), None)
        if not entry:
            for candidate in ["index.js", "index.ts", "main.js", "app.js", "src/index.js"]:
                if (root / candidate).exists():
                    entry = candidate
                    break
        if entry and (root / str(entry)).exists():
            return ProjectConfig(
                project_type="Node.js (CLI/Script)",
                install_cmd=[npm, "install", "--legacy-peer-deps"],
                start_cmd=[node, str(entry)],
                port=0,
                env_vars={},
                is_web=False,
            )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. PYTHON
    # ═══════════════════════════════════════════════════════════════════════
    has_req = _has(root, "requirements.txt")
    has_pyp = _has(root, "pyproject.toml")
    req     = _read_text(root / "requirements.txt") if has_req else ""

    if has_req or has_pyp:
        # FastAPI
        if ("fastapi" in req or "uvicorn" in req) and _has(root, "main.py"):
            return ProjectConfig(
                project_type="FastAPI",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[_python(), "-m", "uvicorn", "main:app",
                           "--host", "0.0.0.0", "--port", str(port)],
                port=port,
                env_vars={"PORT": str(port)},
                is_web=True,
            )

        # Django
        if _has(root, "manage.py"):
            return ProjectConfig(
                project_type="Django",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[_python(), "manage.py", "runserver", f"0.0.0.0:{port}"],
                port=port,
                env_vars={"PORT": str(port)},
                is_web=True,
            )

        # Flask
        flask_entry = next(
            (c for c in ["app.py", "wsgi.py", "run.py", "server.py", "application.py"]
             if (root / c).exists()),
            None,
        )
        if flask_entry and "flask" in req:
            return ProjectConfig(
                project_type="Flask",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"],
                start_cmd=[_python(), flask_entry],
                port=port,
                env_vars={
                    "FLASK_APP": flask_entry, "FLASK_ENV": "development",
                    "FLASK_RUN_PORT": str(port), "PORT": str(port),
                },
                is_web=True,
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
                is_web=True,
            )

        # Generic Python script
        py_entry = next(
            (c for c in ["main.py", "app.py", "run.py", "index.py", "solution.py"]
             if (root / c).exists()),
            None,
        )
        if not py_entry:
            py_files = list(root.glob("*.py"))
            if py_files:
                py_entry = py_files[0].name
        if py_entry:
            return ProjectConfig(
                project_type="Python Script",
                install_cmd=_pip() + ["install", "-r", "requirements.txt"] if has_req else [],
                start_cmd=[_python(), py_entry],
                port=0,
                env_vars={},
                is_web=False,
            )

    # Python without requirements.txt
    py_files = list(root.glob("*.py"))
    if py_files:
        entry = next(
            (p for p in py_files if p.stem in ("main", "app", "run", "index", "solution")),
            py_files[0],
        )
        return ProjectConfig(
            project_type="Python Script",
            install_cmd=[],
            start_cmd=[_python(), entry.name],
            port=0,
            env_vars={},
            is_web=False,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 3. JAVA
    # ═══════════════════════════════════════════════════════════════════════
    mvn   = shutil.which("mvn") or "mvn"
    gradlew = "./gradlew" if not IS_WINDOWS else r"gradlew.bat"

    if _has(root, "pom.xml"):
        return ProjectConfig(
            project_type="Java (Maven)",
            install_cmd=[mvn, "compile", "-q", "-DskipTests"],
            start_cmd=[mvn, "exec:java", "-q"],
            port=0,
            env_vars={},
            is_web=False,
        )

    if _has(root, "build.gradle", "build.gradle.kts"):
        gradle_cmd = str(root / gradlew) if (root / gradlew).exists() else "gradle"
        return ProjectConfig(
            project_type="Java (Gradle)",
            install_cmd=[gradle_cmd, "compileJava", "-q"],
            start_cmd=[gradle_cmd, "run", "-q"],
            port=0,
            env_vars={},
            is_web=False,
        )

    java_files = _find_files(root, "java")
    if java_files:
        javac = shutil.which("javac") or "javac"
        java  = shutil.which("java") or "java"
        # Find the main class heuristically
        main_file = next(
            (f for f in java_files if "main" in f.stem.lower() or "Main" in f.stem),
            java_files[0],
        )
        class_name = main_file.stem
        return ProjectConfig(
            project_type="Java",
            install_cmd=[javac] + [str(f) for f in java_files],
            start_cmd=[java, class_name],
            port=0,
            env_vars={},
            is_web=False,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 4. C / C++
    # ═══════════════════════════════════════════════════════════════════════
    cpp_files = _find_files(root, "cpp") + _find_files(root, "cc")
    c_files   = _find_files(root, "c")

    gcc  = shutil.which("gcc")  or "gcc"
    gpp  = shutil.which("g++")  or "g++"
    out  = "a.out" if not IS_WINDOWS else "a.exe"

    if cpp_files:
        sources = [str(f) for f in cpp_files[:10]]
        return ProjectConfig(
            project_type="C++",
            install_cmd=[gpp] + sources + ["-o", out, "-std=c++17"],
            start_cmd=[str(root / out)],
            port=0,
            env_vars={},
            is_web=False,
        )

    if c_files:
        sources = [str(f) for f in c_files[:10]]
        return ProjectConfig(
            project_type="C",
            install_cmd=[gcc] + sources + ["-o", out],
            start_cmd=[str(root / out)],
            port=0,
            env_vars={},
            is_web=False,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 5. RUST
    # ═══════════════════════════════════════════════════════════════════════
    if _has(root, "Cargo.toml"):
        cargo = shutil.which("cargo") or "cargo"
        return ProjectConfig(
            project_type="Rust",
            install_cmd=[cargo, "build", "--release", "-q"],
            start_cmd=[cargo, "run", "--release", "-q"],
            port=0,
            env_vars={},
            is_web=False,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 6. RUBY
    # ═══════════════════════════════════════════════════════════════════════
    if _has(root, "Gemfile"):
        ruby   = shutil.which("ruby") or "ruby"
        bundle = shutil.which("bundle") or "bundle"
        # Rails is web; generic Ruby is terminal
        gemfile = _read_text(root / "Gemfile")
        if "rails" in gemfile:
            return ProjectConfig(
                project_type="Ruby on Rails",
                install_cmd=[bundle, "install"],
                start_cmd=[bundle, "exec", "rails", "server", "-p", str(port), "-b", "0.0.0.0"],
                port=port,
                env_vars={"PORT": str(port)},
                is_web=True,
            )
        entry = next(
            (c for c in ["main.rb", "app.rb", "run.rb", "index.rb"] if (root / c).exists()),
            None,
        )
        return ProjectConfig(
            project_type="Ruby",
            install_cmd=[bundle, "install"] if _has(root, "Gemfile.lock") else [],
            start_cmd=[ruby, entry or "main.rb"],
            port=0,
            env_vars={},
            is_web=False,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 7. GO
    # ═══════════════════════════════════════════════════════════════════════
    if _has(root, "go.mod"):
        go = shutil.which("go") or "go"
        go_text = _read_text(root / "go.mod")
        return ProjectConfig(
            project_type="Go",
            install_cmd=[go, "mod", "download"],
            start_cmd=[go, "run", "."],
            port=port,
            env_vars={"PORT": str(port)},
            is_web=True,   # most Go repos with go.mod serve HTTP; adjust if needed
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 8. PHP
    # ═══════════════════════════════════════════════════════════════════════
    if _has(root, "composer.json") or list(root.glob("*.php")):
        php = shutil.which("php") or "php"
        entry = next(
            (c for c in ["index.php", "main.php", "app.php"] if (root / c).exists()),
            "index.php",
        )
        return ProjectConfig(
            project_type="PHP",
            install_cmd=[],
            start_cmd=[php, "-S", f"0.0.0.0:{port}", "-t", "."],
            port=port,
            env_vars={"PORT": str(port)},
            is_web=True,
        )

    raise ValueError(
        "Could not detect the project type. "
        "Supported: Next.js, Vite, CRA, Angular, Nuxt, Node.js, FastAPI, Flask, "
        "Django, Streamlit, Python, Java (Maven/Gradle), C, C++, Rust, Ruby, Go, PHP."
    )
