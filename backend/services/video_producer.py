"""
video_producer.py — Post-process the raw Playwright .webm recording
into a polished cinematic .mp4 with intro/outro and color grading.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np
from moviepy.editor import (
    VideoFileClip,
    VideoClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFont

# ── Constants ────────────────────────────────────────────────────────────────
W, H = 1280, 720
FPS = 24
BG       = (8,  8,  16)
ACCENT   = (100, 220, 180)   # teal-green
ACCENT2  = (220, 130, 255)   # purple
TEXT_COL = (220, 220, 235)
DIM_COL  = (90,  95, 110)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONTS_DIR  = ASSETS_DIR / "fonts"


# ── Font helper ───────────────────────────────────────────────────────────────
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "JetBrainsMono-Bold.ttf" if bold else "JetBrainsMono-Regular.ttf"
    for path in [FONTS_DIR / name, Path("arial.ttf")]:
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    return ImageFont.load_default()


# ── Easing ───────────────────────────────────────────────────────────────────
def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _fade(t: float, dur: float, fi: float = 0.4, fo: float = 0.4) -> float:
    a = min(t / fi, 1.0) if fi > 0 else 1.0
    b = min((dur - t) / fo, 1.0) if fo > 0 else 1.0
    return max(0.0, min(a, b))


# ── Intro frame renderer ─────────────────────────────────────────────────────
def _intro_frame(repo_name: str, dur: float = 3.5) -> Callable[[float], np.ndarray]:
    def make(t: float) -> np.ndarray:
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        alpha = _fade(t, dur)

        # Animated accent bars
        bar_w = int(W * _ease_out(min(t / 1.2, 1.0)))
        draw.rectangle([0,     0,     bar_w, 5],     fill=ACCENT)
        draw.rectangle([W - bar_w, H - 5, W, H], fill=ACCENT2)

        # Grid dots (subtle)
        for gx in range(0, W, 60):
            for gy in range(0, H, 60):
                draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=(30, 34, 50))

        # "LIVE PREVIEW" badge
        badge_font = _font(13)
        draw.rounded_rectangle([W // 2 - 72, H // 2 - 110, W // 2 + 72, H // 2 - 88],
                                radius=6, fill=(20, 25, 45))
        draw.text((W // 2, H // 2 - 99), "⬤  LIVE PREVIEW",
                  font=badge_font, fill=ACCENT, anchor="mm")

        # Repo name
        label = repo_name if len(repo_name) < 40 else repo_name[-39:]
        draw.text((W // 2, H // 2 - 30), f"/{label}",
                  font=_font(52, bold=True), fill=ACCENT, anchor="mm")

        # Sub-label
        draw.text((W // 2, H // 2 + 40),
                  "Recorded by ScriptCinema 🎬",
                  font=_font(18), fill=TEXT_COL, anchor="mm")

        draw.text((W // 2, H // 2 + 78),
                  "github.com/Adityadav999/ScriptCinema",
                  font=_font(13), fill=DIM_COL, anchor="mm")

        arr = np.array(img, dtype=np.float32)
        return np.clip(arr * alpha, 0, 255).astype(np.uint8)

    return make


# ── Outro frame renderer ─────────────────────────────────────────────────────
def _outro_frame(repo_name: str, dur: float = 2.5) -> Callable[[float], np.ndarray]:
    def make(t: float) -> np.ndarray:
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        alpha = _fade(t, dur, fi=0.5, fo=0.0)

        bar_w = int(W * _ease_out(min(t / 1.0, 1.0)))
        draw.rectangle([0, 0, bar_w, 5], fill=ACCENT)
        draw.rectangle([W - bar_w, H - 5, W, H], fill=ACCENT2)

        draw.text((W // 2, H // 2 - 50), "🎬 ScriptCinema",
                  font=_font(52, bold=True), fill=ACCENT, anchor="mm")
        draw.text((W // 2, H // 2 + 20),
                  "Turning GitHub Repos into Cinematic Videos",
                  font=_font(20), fill=TEXT_COL, anchor="mm")
        draw.text((W // 2, H // 2 + 62),
                  f"Recorded: {repo_name}",
                  font=_font(14), fill=DIM_COL, anchor="mm")

        arr = np.array(img, dtype=np.float32)
        return np.clip(arr * alpha, 0, 255).astype(np.uint8)

    return make


# ── Vignette ─────────────────────────────────────────────────────────────────
_vignette_cache: Optional[np.ndarray] = None


def _vignette_mask() -> np.ndarray:
    global _vignette_cache
    if _vignette_cache is None:
        Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
        cx, cy = W / 2, H / 2
        dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
        _vignette_cache = np.clip(1.0 - dist * 0.45, 0.25, 1.0)[:, :, np.newaxis]
    return _vignette_cache


def _apply_grade(frame: np.ndarray) -> np.ndarray:
    """Vignette + slight contrast boost."""
    f = frame.astype(np.float32)
    # Contrast
    f = np.clip((f - 128) * 1.08 + 128, 0, 255)
    # Vignette
    f = f * _vignette_mask()
    return np.clip(f, 0, 255).astype(np.uint8)


# ── Public API ────────────────────────────────────────────────────────────────
def produce_video(
    webm_path: str,
    output_path: str,
    repo_name: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Assemble the final cinematic MP4:
      intro (3.5s) + graded browser recording + outro (2.5s)
    """
    def _p(msg: str):
        if on_progress:
            on_progress(msg)

    _p("Loading browser recording…")
    raw = VideoFileClip(webm_path)

    # Resize to target resolution if Playwright gave us something different
    if raw.size != [W, H]:
        raw = raw.resize((W, H))

    _p("Applying cinematic color grade…")
    graded = raw.fl_image(_apply_grade)

    _p("Rendering intro card…")
    intro_dur = 3.5
    intro = VideoClip(
        _intro_frame(repo_name, intro_dur),
        duration=intro_dur,
    )

    _p("Rendering outro card…")
    outro_dur = 2.5
    outro = VideoClip(
        _outro_frame(repo_name, outro_dur),
        duration=outro_dur,
    )

    _p("Assembling final video…")
    final = concatenate_videoclips([intro, graded, outro], method="compose")

    _p("Encoding MP4…")
    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio=False,
        logger=None,
        preset="ultrafast",
    )

    raw.close()
    return output_path
