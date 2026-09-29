"""
ScriptCinema Backend — FastAPI entry point
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers.generate import router as generate_router

load_dotenv()

# ── Ensure output directory exists ──────────────────────────────────────────
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "outputs"))
OUTPUT_DIR.mkdir(exist_ok=True)

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="ScriptCinema API",
    description="Transform any GitHub repository into a cinematic video.",
    version="1.0.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving for generated videos ──────────────────────────────
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(generate_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "ScriptCinema API is running 🎬"}


@app.get("/health")
async def health():
    return {"status": "ok"}
