"""
video_producer.py — Post-process recordings into cinematic MP4s.

Two modes:
  produce_video()          — web projects  (Playwright .webm → graded MP4)
  produce_terminal_video() — non-web projects (captured output → terminal cinema MP4)
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

# ── Shared constants ──────────────────────────────────────────────────────────
W, H = 1280, 720
FPS  = 24
BG       = (8,  8,  16)
ACCENT   = (100, 220, 180)   # teal-green
ACCENT2  = (220, 130, 255)   # purple
TEXT_COL = (220, 220, 235)
DIM_COL  = (90,  95, 110)

# Terminal palette
TERM_BG     = (6, 8, 18)
TERM_PROMPT = (100, 220, 180)
TERM_OUTPUT = (210, 215, 230)
TERM_ERROR  = (255, 100, 110)
TERM_DIM    = (60,  65,  85)
TERM_CURSOR = (100, 220, 180)

MARGIN_X  = 54
MARGIN_Y  = 60
LINE_H    = 26
MAX_LINES = (H - MARGIN_Y * 2) // LINE_H

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


# ── Easing / alpha ────────────────────────────────────────────────────────────
def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _fade(t: float, dur: float, fi: float = 0.4, fo: float = 0.4) -> float:
    a = min(t / fi, 1.0) if fi > 0 else 1.0
    b = min((dur - t) / fo, 1.0) if fo > 0 else 1.0
    return max(0.0, min(a, b))


# ── Shared intro card ─────────────────────────────────────────────────────────
def _intro_frame(repo_name: str, dur: float = 3.5, badge: str = "⬤  LIVE PREVIEW") -> Callable:
    def make(t: float) -> np.ndarray:
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        alpha = _fade(t, dur)

        bar_w = int(W * _ease_out(min(t / 1.2, 1.0)))
        draw.rectangle([0, 0, bar_w, 5], fill=ACCENT)
        draw.rectangle([W - bar_w, H - 5, W, H], fill=ACCENT2)

        for gx in range(0, W, 60):
            for gy in range(0, H, 60):
                draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=(30, 34, 50))

        draw.rounded_rectangle(
            [W // 2 - 80, H // 2 - 112, W // 2 + 80, H // 2 - 88],
            radius=6, fill=(20, 25, 45),
        )
        draw.text((W // 2, H // 2 - 100), badge,
                  font=_font(13), fill=ACCENT, anchor="mm")

        label = repo_name if len(repo_name) < 40 else repo_name[-39:]
        draw.text((W // 2, H // 2 - 28), f"/{label}",
                  font=_font(48, bold=True), fill=ACCENT, anchor="mm")

        draw.text((W // 2, H // 2 + 40), "Recorded by ScriptCinema 🎬",
                  font=_font(18), fill=TEXT_COL, anchor="mm")
        draw.text((W // 2, H // 2 + 76), "github.com/Adityadav999/ScriptCinema",
                  font=_font(13), fill=DIM_COL, anchor="mm")

        arr = np.array(img, dtype=np.float32)
        return np.clip(arr * alpha, 0, 255).astype(np.uint8)
    return make


# ── Shared outro card ─────────────────────────────────────────────────────────
def _outro_frame(repo_name: str, dur: float = 2.5) -> Callable:
    def make(t: float) -> np.ndarray:
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        alpha = _fade(t, dur, fi=0.5, fo=0.0)

        bar_w = int(W * _ease_out(min(t / 1.0, 1.0)))
        draw.rectangle([0, 0, bar_w, 5], fill=ACCENT)
        draw.rectangle([W - bar_w, H - 5, W, H], fill=ACCENT2)

        draw.text((W // 2, H // 2 - 50), "🎬 ScriptCinema",
                  font=_font(52, bold=True), fill=ACCENT, anchor="mm")
        draw.text((W // 2, H // 2 + 20), "Turning GitHub Repos into Cinematic Videos",
                  font=_font(20), fill=TEXT_COL, anchor="mm")
        draw.text((W // 2, H // 2 + 62), f"Recorded: {repo_name}",
                  font=_font(14), fill=DIM_COL, anchor="mm")

        arr = np.array(img, dtype=np.float32)
        return np.clip(arr * alpha, 0, 255).astype(np.uint8)
    return make


# ── Vignette / grade (web only) ───────────────────────────────────────────────
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
    f = frame.astype(np.float32)
    f = np.clip((f - 128) * 1.08 + 128, 0, 255)
    f = f * _vignette_mask()
    return np.clip(f, 0, 255).astype(np.uint8)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — WEB RECORDING
# ═══════════════════════════════════════════════════════════════════════════════
def produce_video(
    webm_path: str,
    output_path: str,
    repo_name: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> str:
    """Wrap a Playwright .webm with cinematic intro/grade/outro → MP4."""
    def _p(msg: str):
        if on_progress:
            on_progress(msg)

    _p("Loading browser recording…")
    raw = VideoFileClip(webm_path)
    if raw.size != [W, H]:
        raw = raw.resize((W, H))

    _p("Applying cinematic color grade…")
    graded = raw.fl_image(_apply_grade)

    _p("Rendering intro card…")
    intro_dur = 3.5
    intro = VideoClip(_intro_frame(repo_name, intro_dur), duration=intro_dur)

    _p("Rendering outro card…")
    outro_dur = 2.5
    outro = VideoClip(_outro_frame(repo_name, outro_dur), duration=outro_dur)

    _p("Assembling final video…")
    final = concatenate_videoclips([intro, graded, outro], method="compose")

    _p("Encoding MP4…")
    final.write_videofile(
        output_path, fps=FPS, codec="libx264",
        audio=False, logger=None, preset="ultrafast",
    )
    raw.close()
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — TERMINAL CINEMA (non-web projects)
# ═══════════════════════════════════════════════════════════════════════════════

def _term_colour(line: str) -> tuple:
    lo = line.lower()
    if lo.startswith(("$", ">", "#", "→", "✓", "⏱", "⬤")):
        return TERM_PROMPT
    if any(w in lo for w in ("error", "exception", "traceback", "fatal", "⚠", "warning")):
        return TERM_ERROR
    return TERM_OUTPUT


def _wrap_line(line: str, font, max_px: int) -> list[str]:
    """Soft-wrap a single line to fit within max_px."""
    try:
        if font.getlength(line) <= max_px:
            return [line]
    except AttributeError:
        if len(line) * 9 <= max_px:
            return [line]

    words, current, result = line.split(" "), "", []
    for word in words:
        test = f"{current} {word}".lstrip()
        try:
            fits = font.getlength(test) <= max_px
        except AttributeError:
            fits = len(test) * 9 <= max_px
        if not fits and current:
            result.append(current)
            current = word
        else:
            current = test
    if current:
        result.append(current)
    return result or [""]


def _build_terminal_frames(
    lines: list[str],
    project_type: str,
    repo_name: str,
    run_cmd: str,
) -> tuple[list[np.ndarray], float]:
    """Pre-render all terminal animation frames. Returns (frames, fps)."""
    term_font  = _font(15)
    header_fnt = _font(13, bold=True)
    max_w      = W - MARGIN_X * 2

    # Build display lines: prompt first, then all output
    display: list[tuple[str, tuple]] = [
        (f"$ {run_cmd}", TERM_PROMPT),
    ]
    for raw in lines:
        colour = _term_colour(raw)
        for wrapped in _wrap_line(raw, term_font, max_w):
            display.append((wrapped, colour))

    total = len(display)
    # Speed: 5 lines/sec for short output, slower for long output
    LINE_DELAY = max(0.05, min(0.35, 18.0 / max(total, 1)))
    HOLD       = 2.5
    total_dur  = total * LINE_DELAY + HOLD
    n_frames   = int(total_dur * FPS) + 1

    def _render(n_vis: int, cursor_on: bool) -> np.ndarray:
        img  = Image.new("RGB", (W, H), TERM_BG)
        draw = ImageDraw.Draw(img)

        # Header bar
        draw.rectangle([0, 0, W, 40], fill=(12, 14, 28))
        draw.text((MARGIN_X, 12), f"  {project_type}  ·  {repo_name}",
                  font=header_fnt, fill=TERM_PROMPT)
        draw.rectangle([0, 40, W, 42], fill=TERM_PROMPT)

        # Scrolling window — show last MAX_LINES of visible lines
        visible = display[:n_vis]
        start   = max(0, len(visible) - MAX_LINES)
        window  = visible[start:]

        for i, (text, colour) in enumerate(window):
            y = MARGIN_Y + i * LINE_H
            draw.text((8,         y), f"{start + i + 1:>3}", font=term_font, fill=TERM_DIM)
            draw.text((MARGIN_X,  y), text,                  font=term_font, fill=colour)

        # Blinking cursor after last visible line
        if cursor_on and window:
            last_y = MARGIN_Y + (len(window) - 1) * LINE_H
            try:
                cx = MARGIN_X + int(term_font.getlength(window[-1][0])) + 4
            except AttributeError:
                cx = MARGIN_X + len(window[-1][0]) * 9 + 4
            draw.rectangle([cx, last_y + 3, cx + 10, last_y + LINE_H - 3], fill=TERM_CURSOR)

        # Bottom bar
        draw.rectangle([0, H - 30, W, H], fill=(12, 14, 28))
        draw.text((MARGIN_X, H - 21),
                  "ScriptCinema  ·  github.com/Adityadav999/ScriptCinema",
                  font=_font(11), fill=TERM_DIM)

        return np.array(img, dtype=np.uint8)

    frames: list[np.ndarray] = []
    for fi in range(n_frames):
        t      = fi / FPS
        n_vis  = min(int(t / LINE_DELAY) + 1, total)
        blink  = int(t * 2) % 2 == 0
        frames.append(_render(n_vis, blink))

    return frames, FPS


def produce_terminal_video(
    output_lines: list[str],
    output_path: str,
    repo_name: str,
    project_type: str,
    run_cmd: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Render a terminal-cinema MP4 from captured program stdout/stderr.
    Layout: intro card (3s) → scrolling terminal output → outro card (2.5s)
    """
    def _p(msg: str):
        if on_progress:
            on_progress(msg)

    _p("Rendering terminal frames…")
    frames, fps = _build_terminal_frames(output_lines, project_type, repo_name, run_cmd)

    # Pre-rendered frames → VideoClip
    def _make_frame(t: float) -> np.ndarray:
        idx = min(int(t * fps), len(frames) - 1)
        return frames[idx]

    term_dur  = len(frames) / fps
    term_clip = VideoClip(_make_frame, duration=term_dur)

    _p("Rendering intro card…")
    intro_dur = 3.0
    intro = VideoClip(
        _intro_frame(repo_name, intro_dur, badge="⬤  TERMINAL RECORDING"),
        duration=intro_dur,
    )

    _p("Rendering outro card…")
    outro_dur = 2.5
    outro = VideoClip(_outro_frame(repo_name, outro_dur), duration=outro_dur)

    _p("Assembling final video…")
    final = concatenate_videoclips([intro, term_clip, outro], method="compose")

    _p("Encoding MP4…")
    final.write_videofile(
        output_path, fps=FPS, codec="libx264",
        audio=False, logger=None, preset="ultrafast",
    )
    return output_path
