"""
Generate router — handles job creation and status polling.
"""
import asyncio
import uuid
from pathlib import Path
from typing import Optional
import os

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl

from services.github_fetcher import fetch_repo_data
from services.scene_builder import build_scenes
from services.video_renderer import render_video

load_dotenv()

router = APIRouter()

# ── In-memory job store (fine for single-server v1) ──────────────────────────
# Structure: { job_id: { status, progress, scene, video_url, error } }
_jobs: dict[str, dict] = {}

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "outputs"))


# ── Request / Response models ─────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    repo_url: str


class GenerateResponse(BaseModel):
    job_id: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    status: str           # "queued" | "running" | "done" | "error"
    progress: int         # 0-100
    scene: Optional[str]  # Current scene name
    video_url: Optional[str]
    error: Optional[str]


# ── Background worker ─────────────────────────────────────────────────────────
def _run_pipeline(job_id: str, repo_url: str):
    """Runs the full ScriptCinema pipeline synchronously in a thread."""
    job = _jobs[job_id]
    try:
        # Step 1: Fetch repo data
        job["status"] = "running"
        job["scene"] = "Fetching repository data…"
        job["progress"] = 5

        repo_data = fetch_repo_data(repo_url)

        # Step 2: Build scenes
        job["scene"] = "Building scenes…"
        job["progress"] = 15
        scenes = build_scenes(repo_data)

        # Step 3: Render video
        output_path = str(OUTPUT_DIR / f"{job_id}.mp4")

        def on_progress(scene_name: str, pct: int):
            job["scene"] = scene_name
            job["progress"] = 15 + int(pct * 0.85)

        render_video(scenes, output_path, progress_callback=on_progress)

        # Done
        job["status"] = "done"
        job["progress"] = 100
        job["scene"] = "Complete"
        job["video_url"] = f"/outputs/{job_id}.mp4"

    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        job["progress"] = 0


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    """
    Start a video generation job for the given GitHub repo URL.
    Returns a job_id to poll for status.
    """
    repo_url = request.repo_url.strip()
    if "github.com" not in repo_url:
        raise HTTPException(status_code=400, detail="URL must be a GitHub repository link.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "scene": "Queued",
        "video_url": None,
        "error": None,
    }

    # Run in a thread so we don't block the event loop
    background_tasks.add_task(
        asyncio.get_event_loop().run_in_executor,
        None,
        _run_pipeline,
        job_id,
        repo_url,
    )

    return GenerateResponse(job_id=job_id, message="Job started successfully.")


@router.get("/status/{job_id}", response_model=StatusResponse)
async def status(job_id: str):
    """Poll the status of a generation job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        scene=job.get("scene"),
        video_url=job.get("video_url"),
        error=job.get("error"),
    )


@router.get("/jobs")
async def list_jobs():
    """List all jobs (for debugging)."""
    return {"jobs": list(_jobs.keys()), "count": len(_jobs)}
