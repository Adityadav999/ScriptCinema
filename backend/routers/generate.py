"""
generate.py — API router for the ScriptCinema pipeline.

POST /api/generate       → kick off the pipeline, returns job_id
GET  /api/status/:id     → poll for progress
DELETE /api/jobs/:id     → delete job + video

Pipeline branches automatically:
  is_web=True  → clone → detect → install → start server → wait → record browser → cinematic MP4
  is_web=False → clone → detect → install/compile → run → capture output → terminal cinema MP4
"""
import asyncio
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from services.repo_cloner import clone_repo, cleanup_repo
from services.project_detector import detect_project
from services.project_runner import ProjectRunner
from services.browser_actor import record_session
from services.video_producer import produce_video, produce_terminal_video

load_dotenv()

router = APIRouter()

_jobs: dict[str, dict] = {}

OUTPUT_DIR     = Path(os.getenv("OUTPUT_DIR", "outputs"))
RECORDINGS_DIR = OUTPUT_DIR / "recordings"
OUTPUT_DIR.mkdir(exist_ok=True)
RECORDINGS_DIR.mkdir(exist_ok=True)


# ── Pydantic models ───────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    repo_url: str


class GenerateResponse(BaseModel):
    job_id: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    step: Optional[str]
    video_url: Optional[str]
    error: Optional[str]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _set(job_id: str, step: str, progress: int):
    if job_id in _jobs:
        _jobs[job_id]["step"]     = step
        _jobs[job_id]["progress"] = progress


def _repo_name(repo_url: str) -> str:
    return repo_url.split("github.com/")[-1].strip("/")


# ═══════════════════════════════════════════════════════════════════════════════
# WEB PIPELINE  (browser recording)
# ═══════════════════════════════════════════════════════════════════════════════
def _run_web_pipeline(job_id: str, repo_url: str, repo_dir: str, runner: ProjectRunner):
    config = runner.config

    # Install deps
    _set(job_id, f"📦  Installing {config.project_type} dependencies…", 20)
    runner.install(timeout=300)
    _set(job_id, "✓  Dependencies installed", 44)

    # Start server
    _set(job_id, f"🚀  Starting {config.project_type} server on :{config.port}…", 48)
    runner.start()

    # Wait for HTTP response (any status code = server is up)
    _set(job_id, "⏳  Waiting for server to respond…", 54)
    runner.wait_for_ready(timeout=120)
    _set(job_id, "✅  Server is live!", 60)

    # Record browser session
    _set(job_id, "🎬  Launching Playwright browser…", 62)
    rec_dir = str(RECORDINGS_DIR / job_id)

    def on_browser(msg: str):
        _set(job_id, f"🎬  {msg}", 66)

    webm_path = record_session(
        port=config.port,
        output_dir=rec_dir,
        on_progress=on_browser,
    )

    runner.stop()

    # Cinematic post-processing
    _set(job_id, "🎞️  Rendering cinematic video…", 78)
    output_path = str(OUTPUT_DIR / f"{job_id}.mp4")

    def on_video(msg: str):
        _set(job_id, f"🎞️  {msg}", 85)

    produce_video(webm_path, output_path, _repo_name(repo_url), on_video)
    shutil.rmtree(rec_dir, ignore_errors=True)

    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# TERMINAL PIPELINE  (non-web: Python, C/C++, Java, Rust, …)
# ═══════════════════════════════════════════════════════════════════════════════
def _run_terminal_pipeline(job_id: str, repo_url: str, repo_dir: str, runner: ProjectRunner):
    config = runner.config

    # Install / compile
    if config.install_cmd:
        verb = "Compiling" if config.project_type in ("C", "C++", "Java", "Rust") else "Installing"
        _set(job_id, f"⚙️  {verb} {config.project_type} project…", 20)
        runner.install(timeout=300)
        _set(job_id, f"✓  {verb} done", 50)
    else:
        _set(job_id, f"✓  No install step for {config.project_type}", 50)

    # Run the program and capture output
    _set(job_id, f"▶️  Running {config.project_type} program…", 55)
    run_label = " ".join(config.start_cmd[-2:])  # short label for display

    def on_run(msg: str):
        _set(job_id, f"▶️  {msg}", 60)

    output_lines = runner.run_and_capture(timeout=30)

    _set(job_id, f"✓  Captured {len(output_lines)} lines of output", 65)

    # Terminal cinema rendering
    _set(job_id, "🎞️  Rendering terminal cinema…", 70)
    output_path = str(OUTPUT_DIR / f"{job_id}.mp4")

    def on_video(msg: str):
        _set(job_id, f"🎞️  {msg}", 80)

    produce_terminal_video(
        output_lines=output_lines,
        output_path=output_path,
        repo_name=_repo_name(repo_url),
        project_type=config.project_type,
        run_cmd=run_label,
        on_progress=on_video,
    )

    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════
def _run_pipeline(job_id: str, repo_url: str):
    job      = _jobs[job_id]
    repo_dir = None
    runner   = None

    try:
        job["status"] = "running"

        # 1. Clone
        _set(job_id, "⬇️  Cloning repository…", 5)
        repo_dir = clone_repo(repo_url)

        # 2. Detect stack
        _set(job_id, "🔍  Detecting project type…", 12)
        config = detect_project(repo_dir)
        _set(job_id, f"✓  Detected: {config.project_type}", 16)
        job["project_type"] = config.project_type
        job["is_web"]       = config.is_web

        runner = ProjectRunner(repo_dir, config)

        # 3. Branch on web vs non-web
        if config.is_web:
            output_path = _run_web_pipeline(job_id, repo_url, repo_dir, runner)
        else:
            output_path = _run_terminal_pipeline(job_id, repo_url, repo_dir, runner)

        # Done
        job["status"]    = "done"
        job["progress"]  = 100
        job["step"]      = "✅  Your cinematic video is ready!"
        job["video_url"] = f"/outputs/{job_id}.mp4"

    except Exception as exc:
        job["status"] = "error"
        job["error"]  = str(exc)
        job["step"]   = "❌  Error"

    finally:
        if runner:
            try:
                runner.stop()
            except Exception:
                pass
        if repo_dir:
            cleanup_repo(repo_dir)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    repo_url = request.repo_url.strip()
    if "github.com" not in repo_url:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid GitHub repository URL.",
        )

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status":       "queued",
        "progress":     0,
        "step":         "⏳  Queued…",
        "video_url":    None,
        "error":        None,
        "project_type": None,
        "is_web":       None,
    }

    background_tasks.add_task(
        asyncio.get_event_loop().run_in_executor,
        None,
        _run_pipeline,
        job_id,
        repo_url,
    )

    return GenerateResponse(job_id=job_id, message="Pipeline started.")


@router.get("/status/{job_id}", response_model=StatusResponse)
async def status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        step=job.get("step"),
        video_url=job.get("video_url"),
        error=job.get("error"),
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    _jobs.pop(job_id, None)
    video = OUTPUT_DIR / f"{job_id}.mp4"
    if video.exists():
        video.unlink()
    return {"deleted": job_id}
