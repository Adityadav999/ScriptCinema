"""
generate.py — API router for the ScriptCinema pipeline.

POST /api/generate  → kick off the pipeline, returns job_id
GET  /api/status/:id → poll for progress
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
from services.video_producer import produce_video

load_dotenv()

router = APIRouter()

# ── Job store (in-memory, fine for single-server v1) ─────────────────────────
_jobs: dict[str, dict] = {}

OUTPUT_DIR      = Path(os.getenv("OUTPUT_DIR", "outputs"))
RECORDINGS_DIR  = OUTPUT_DIR / "recordings"
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
    status: str          # queued | running | done | error
    progress: int        # 0-100
    step: Optional[str]  # Human-readable current step label
    video_url: Optional[str]
    error: Optional[str]


# ── Job helpers ───────────────────────────────────────────────────────────────
def _set(job_id: str, step: str, progress: int):
    if job_id in _jobs:
        _jobs[job_id]["step"]     = step
        _jobs[job_id]["progress"] = progress


# ── Pipeline (runs in a thread pool via BackgroundTasks) ──────────────────────
def _run_pipeline(job_id: str, repo_url: str):
    job       = _jobs[job_id]
    repo_dir  = None
    runner    = None

    try:
        job["status"] = "running"

        # ── 1. Clone ─────────────────────────────────────────────────────────
        _set(job_id, "⬇️  Cloning repository…", 5)
        repo_dir = clone_repo(repo_url)

        # ── 2. Detect stack ──────────────────────────────────────────────────
        _set(job_id, "🔍  Detecting project type…", 12)
        config = detect_project(repo_dir)
        _set(job_id, f"✓  Detected: {config.project_type}", 15)

        # ── 3. Install dependencies ──────────────────────────────────────────
        _set(job_id, f"📦  Installing {config.project_type} dependencies…", 20)
        runner = ProjectRunner(repo_dir, config)
        runner.install(timeout=300)
        _set(job_id, "✓  Dependencies installed", 45)

        # ── 4. Start server ──────────────────────────────────────────────────
        _set(job_id, f"🚀  Starting {config.project_type} server on port {config.port}…", 50)
        runner.start()

        # ── 5. Wait for server to be ready ───────────────────────────────────
        _set(job_id, "⏳  Waiting for server to respond…", 55)
        ready = runner.wait_for_ready(timeout=120)
        if not ready:
            raise RuntimeError(
                f"{config.project_type} server did not respond within 120 s. "
                "Check that your repo starts a web server."
            )
        _set(job_id, "✅  Server is live!", 60)

        # ── 6. Record browser session ─────────────────────────────────────────
        _set(job_id, "🎬  Launching browser recorder…", 62)
        rec_dir = str(RECORDINGS_DIR / job_id)

        def on_browser(msg: str):
            _set(job_id, f"🎬  {msg}", 65)

        webm_path = record_session(
            port=config.port,
            output_dir=rec_dir,
            on_progress=on_browser,
        )

        # ── 7. Stop server (no longer needed) ────────────────────────────────
        runner.stop()
        runner = None

        # ── 8. Cinematic post-processing ──────────────────────────────────────
        _set(job_id, "🎞️  Rendering cinematic video…", 78)
        output_path = str(OUTPUT_DIR / f"{job_id}.mp4")
        repo_name   = repo_url.split("github.com/")[-1].strip("/")

        def on_video(msg: str):
            _set(job_id, f"🎞️  {msg}", 85)

        produce_video(webm_path, output_path, repo_name, on_video)

        # ── 9. Cleanup temp recording ─────────────────────────────────────────
        shutil.rmtree(rec_dir, ignore_errors=True)

        # ── Done ──────────────────────────────────────────────────────────────
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
            runner.stop()
        if repo_dir:
            cleanup_repo(repo_dir)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    repo_url = request.repo_url.strip()
    if "github.com" not in repo_url:
        raise HTTPException(status_code=400, detail="Please provide a valid GitHub repository URL.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status":    "queued",
        "progress":  0,
        "step":      "⏳  Queued…",
        "video_url": None,
        "error":     None,
    }

    # Run the CPU-bound pipeline in a thread without blocking the event loop
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
    """Remove a completed job and its output video."""
    _jobs.pop(job_id, None)
    video = OUTPUT_DIR / f"{job_id}.mp4"
    if video.exists():
        video.unlink()
    return {"deleted": job_id}
