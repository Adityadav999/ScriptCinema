"""
Video renderer — converts Scene objects into animated frames and assembles them
into an .mp4 using MoviePy + Pillow.
"""
from __future__ import annotations

import math
import os
import textwrap
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from moviepy.editor import ImageSequenceClip, concatenate_videoclips, VideoClip
from PIL import Image, ImageDraw, ImageFont

from services.scene_builder import Scene

# ── Constants ────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1280, 720
FPS = 24
BG_COLOR = (10, 10, 20)          # Near-black
ACCENT = (100, 220, 180)         # Teal-green
ACCENT2 = (220, 130, 255)        # Purple
TEXT_COLOR = (220, 220, 235)     # Off-white
DIM_COLOR = (100, 105, 120)      # Muted grey
CODE_BG = (18, 20, 35)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

# Language colors (matching GitHub's palette)
LANG_COLORS: dict[str, tuple] = {
    "Python": (53, 114, 165),
    "JavaScript": (241, 224, 90),
    "TypeScript": (43, 116, 137),
    "Java": (176, 114, 25),
    "C++": (243, 75, 125),
    "C": (85, 85, 85),
    "Go": (0, 173, 216),
    "Rust": (222, 165, 132),
    "Ruby": (112, 21, 22),
    "PHP": (79, 93, 149),
    "Swift": (240, 81, 56),
    "Kotlin": (169, 123, 255),
    "HTML": (227, 76, 38),
    "CSS": (86, 61, 124),
    "Shell": (137, 224, 81),
    "Scala": (194, 83, 52),
    "R": (25, 140, 210),
    "Vue": (65, 184, 131),
}
DEFAULT_LANG_COLOR = (120, 130, 145)


# ── Font loader ──────────────────────────────────────────────────────────────
def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try to load JetBrains Mono, fall back to a default font."""
    font_name = "JetBrainsMono-Bold.ttf" if bold else "JetBrainsMono-Regular.ttf"
    font_path = FONTS_DIR / font_name
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()


# ── Drawing helpers ──────────────────────────────────────────────────────────
def _new_frame() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    return img, draw


def _draw_scanlines(draw: ImageDraw.ImageDraw, alpha: int = 15):
    """Subtle scanline overlay for cinematic feel."""
    for y in range(0, HEIGHT, 4):
        draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))


def _draw_gradient_bar(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
                        color: tuple):
    """Draw a rounded gradient-like bar."""
    for i in range(h):
        factor = 1.0 - (i / h) * 0.3
        c = tuple(int(v * factor) for v in color)
        draw.rectangle([x, y + i, x + w, y + i + 1], fill=c)


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _fade(t: float, duration: float, fade_in: float = 0.3, fade_out: float = 0.3) -> float:
    if t < fade_in:
        return t / fade_in
    if t > duration - fade_out:
        return (duration - t) / fade_out
    return 1.0


def _draw_watermark(draw: ImageDraw.ImageDraw):
    font = _load_font(14)
    draw.text((WIDTH - 200, HEIGHT - 28), "🎬 ScriptCinema", fill=DIM_COLOR, font=font)


# ── Scene renderers ──────────────────────────────────────────────────────────

def _render_intro(scene: Scene, t: float) -> np.ndarray:
    img, draw = _new_frame()
    alpha = _fade(t, scene.duration)
    d = scene.data

    # Glowing accent line at top
    bar_w = int(WIDTH * min(t / 1.5, 1.0))
    draw.rectangle([0, 0, bar_w, 4], fill=ACCENT)

    # Repo name
    font_big = _load_font(64, bold=True)
    font_med = _load_font(24)
    font_sm = _load_font(17)

    name = d["repo_name"]
    draw.text((80, 160), f"/{name}", font=font_big, fill=ACCENT)

    # Owner
    draw.text((84, 238), f"by {d['owner']}", font=font_med, fill=DIM_COLOR)

    # Description (wrapped)
    desc = d["description"]
    wrapped = textwrap.wrap(desc, width=70)
    y = 300
    for line in wrapped[:3]:
        draw.text((80, y), line, font=font_sm, fill=TEXT_COLOR)
        y += 28

    # Language + Created
    draw.text((80, HEIGHT - 120), f"Primary Language: {d['language']}", font=font_sm, fill=ACCENT2)
    draw.text((80, HEIGHT - 90), f"Created: {d['created_at']}", font=font_sm, fill=DIM_COLOR)

    # Topics
    tx = 80
    ty = HEIGHT - 55
    for topic in d.get("topics", [])[:5]:
        tag_font = _load_font(13)
        bbox = draw.textbbox((0, 0), f" {topic} ", font=tag_font)
        tw = bbox[2] - bbox[0] + 8
        draw.rounded_rectangle([tx, ty, tx + tw, ty + 22], radius=5, fill=(30, 35, 55))
        draw.text((tx + 4, ty + 4), f" {topic} ", font=tag_font, fill=ACCENT)
        tx += tw + 8

    # Bottom accent line
    draw.rectangle([0, HEIGHT - 4, WIDTH, HEIGHT], fill=ACCENT2)
    _draw_watermark(draw)

    arr = np.array(img).astype(np.float32)
    arr = (arr * alpha).astype(np.uint8)
    return arr


def _render_languages(scene: Scene, t: float) -> np.ndarray:
    img, draw = _new_frame()
    d = scene.data
    langs = d["languages"]

    font_title = _load_font(40, bold=True)
    font_label = _load_font(18)
    font_pct = _load_font(15)

    draw.text((80, 60), "Language Breakdown", font=font_title, fill=TEXT_COLOR)
    draw.rectangle([80, 110, 80 + 60, 114], fill=ACCENT)

    max_pct = max(l["pct"] for l in langs) if langs else 100
    bar_area_w = WIDTH - 320
    bar_h = 32
    gap = 20
    start_y = 160

    for i, lang in enumerate(langs):
        y = start_y + i * (bar_h + gap)
        # Animate bar width
        progress = _ease_out(min(max(t - i * 0.2, 0) / 1.5, 1.0))
        target_w = int((lang["pct"] / max_pct) * bar_area_w)
        bar_w = int(target_w * progress)

        color = LANG_COLORS.get(lang["name"], DEFAULT_LANG_COLOR)

        # Background bar
        draw.rounded_rectangle([200, y, 200 + bar_area_w, y + bar_h], radius=4, fill=(25, 28, 45))
        # Filled bar
        if bar_w > 4:
            _draw_gradient_bar(draw, 200, y, bar_w, bar_h, color)

        # Label
        draw.text((80, y + 7), lang["name"], font=font_label, fill=TEXT_COLOR)
        # Percentage
        if progress > 0.5:
            draw.text((200 + bar_area_w + 12, y + 8), f"{lang['pct']}%", font=font_pct, fill=ACCENT)

    draw.rectangle([0, HEIGHT - 4, WIDTH, HEIGHT], fill=ACCENT)
    _draw_watermark(draw)
    return np.array(img)


def _render_filetree(scene: Scene, t: float) -> np.ndarray:
    img, draw = _new_frame()
    d = scene.data

    font_title = _load_font(38, bold=True)
    font_tree = _load_font(17)

    draw.text((80, 60), "File Structure", font=font_title, fill=TEXT_COLOR)
    draw.rectangle([80, 108, 140, 112], fill=ACCENT2)

    # Repo root
    root_font = _load_font(20, bold=True)
    draw.text((80, 130), f"📦 {d['repo_name']}/", font=root_font, fill=ACCENT)

    tree = d["tree"]
    items_to_show = min(len(tree), int(t / scene.duration * len(tree) * 1.5) + 1)

    for i, item in enumerate(tree[:items_to_show]):
        y = 170 + i * 25
        if y > HEIGHT - 60:
            break
        # Connector line
        draw.line([(100, y + 8), (115, y + 8)], fill=DIM_COLOR, width=1)
        draw.text((120, y), item, font=font_tree, fill=TEXT_COLOR)

    draw.rectangle([0, HEIGHT - 4, WIDTH, HEIGHT], fill=ACCENT2)
    _draw_watermark(draw)
    return np.array(img)


def _render_code(scene: Scene, t: float) -> np.ndarray:
    img, draw = _new_frame()
    d = scene.data

    # Code background panel
    draw.rectangle([60, 40, WIDTH - 60, HEIGHT - 40], fill=CODE_BG)
    draw.rounded_rectangle([60, 40, WIDTH - 60, HEIGHT - 40], radius=10, outline=ACCENT, width=1)

    # Title bar
    draw.rectangle([60, 40, WIDTH - 60, 80], fill=(22, 25, 42))
    draw.ellipse([80, 55, 96, 71], fill=(255, 95, 86))
    draw.ellipse([104, 55, 120, 71], fill=(255, 189, 46))
    draw.ellipse([128, 55, 144, 71], fill=(39, 201, 63))

    filename = d.get("filename", "code")
    font_tab = _load_font(14)
    draw.text((160, 58), filename, font=font_tab, fill=TEXT_COLOR)

    # Code lines
    code = d.get("content", "")
    lines = code.splitlines()
    font_code = _load_font(14)
    font_ln = _load_font(12)

    # Scroll animation: start from top, scroll down over time
    total_lines = len(lines)
    visible = 28
    scroll_progress = _ease_out(min(t / scene.duration, 1.0))
    start_line = int(max(0, total_lines - visible) * scroll_progress)
    visible_lines = lines[start_line: start_line + visible]

    for i, line in enumerate(visible_lines):
        y = 92 + i * 21
        ln_num = start_line + i + 1
        # Line number
        draw.text((72, y), f"{ln_num:3d}", font=font_ln, fill=DIM_COLOR)
        # Code line (truncated)
        truncated = line[:95]
        draw.text((120, y), truncated, font=font_code, fill=TEXT_COLOR)

    _draw_watermark(draw)
    return np.array(img)


def _render_commits(scene: Scene, t: float) -> np.ndarray:
    img, draw = _new_frame()
    d = scene.data
    commits = d["commits"]

    font_title = _load_font(38, bold=True)
    font_sha = _load_font(14)
    font_msg = _load_font(17)
    font_meta = _load_font(13)

    draw.text((80, 55), "Recent Commits", font=font_title, fill=TEXT_COLOR)
    draw.rectangle([80, 105, 140, 109], fill=ACCENT)

    items_to_show = min(len(commits), int(t / scene.duration * len(commits) * 1.8) + 1)

    for i, commit in enumerate(commits[:items_to_show]):
        y = 130 + i * 68

        # Timeline dot + line
        dot_x, dot_y = 90, y + 14
        if i < len(commits) - 1:
            draw.line([(dot_x, dot_y + 12), (dot_x, dot_y + 68)], fill=DIM_COLOR, width=2)
        draw.ellipse([dot_x - 7, dot_y - 7, dot_x + 7, dot_y + 7], fill=ACCENT)

        # SHA badge
        draw.rounded_rectangle([110, y, 165, y + 22], radius=4, fill=(30, 40, 60))
        draw.text((114, y + 4), commit["sha"], font=font_sha, fill=ACCENT2)

        # Commit message
        msg = commit["message"][:75]
        draw.text((172, y + 4), msg, font=font_msg, fill=TEXT_COLOR)

        # Author + date
        meta = f"{commit['author']}  ·  {commit['date']}"
        draw.text((172, y + 28), meta, font=font_meta, fill=DIM_COLOR)

    draw.rectangle([0, HEIGHT - 4, WIDTH, HEIGHT], fill=ACCENT)
    _draw_watermark(draw)
    return np.array(img)


def _render_stats(scene: Scene, t: float) -> np.ndarray:
    img, draw = _new_frame()
    d = scene.data

    font_title = _load_font(40, bold=True)
    font_num = _load_font(52, bold=True)
    font_label = _load_font(18)

    draw.text((80, 55), "Repository Stats", font=font_title, fill=TEXT_COLOR)
    draw.rectangle([80, 108, 200, 112], fill=ACCENT2)

    stats = [
        ("⭐", "Stars", d["stars"], ACCENT),
        ("🍴", "Forks", d["forks"], ACCENT2),
        ("🐛", "Open Issues", d["issues"], (255, 180, 80)),
        ("👁️", "Watchers", d["watchers"], (100, 180, 255)),
        ("👥", "Contributors", d["contributors"], (180, 255, 100)),
    ]

    card_w = 200
    card_h = 140
    cols = 3
    gap = 20
    start_x = (WIDTH - (card_w * cols + gap * (cols - 1))) // 2
    start_y = 160

    for i, (icon, label, value, color) in enumerate(stats):
        col = i % cols
        row = i // cols
        x = start_x + col * (card_w + gap)
        y = start_y + row * (card_h + gap)

        progress = _ease_out(min(max(t - i * 0.15, 0) / 1.2, 1.0))

        # Card background
        draw.rounded_rectangle([x, y, x + card_w, y + card_h], radius=12, fill=(20, 24, 40))
        draw.rounded_rectangle([x, y, x + card_w, y + 4], radius=4, fill=color)

        # Icon
        icon_font = _load_font(28)
        draw.text((x + 16, y + 18), icon, font=icon_font)

        # Value (animated count-up)
        shown_value = int(value * progress)
        num_font = _load_font(36, bold=True)
        draw.text((x + 16, y + 55), f"{shown_value:,}", font=num_font, fill=color)

        # Label
        draw.text((x + 16, y + 105), label, font=font_label, fill=DIM_COLOR)

    draw.text((80, HEIGHT - 50), f"Last updated: {d['updated_at']}", font=font_label, fill=DIM_COLOR)
    draw.rectangle([0, HEIGHT - 4, WIDTH, HEIGHT], fill=ACCENT2)
    _draw_watermark(draw)
    return np.array(img)


def _render_outro(scene: Scene, t: float) -> np.ndarray:
    img, draw = _new_frame()
    d = scene.data
    alpha = _fade(t, scene.duration)

    # Center content
    font_big = _load_font(52, bold=True)
    font_med = _load_font(22)
    font_sm = _load_font(17)
    font_tag = _load_font(15)

    # Animated accent bars
    bar_progress = _ease_out(min(t / 1.0, 1.0))
    bar_w = int(WIDTH * bar_progress)
    draw.rectangle([0, 0, bar_w, 5], fill=ACCENT)
    draw.rectangle([WIDTH - bar_w, HEIGHT - 5, WIDTH, HEIGHT], fill=ACCENT2)

    # Main text
    draw.text((WIDTH // 2, HEIGHT // 2 - 80), "🎬 ScriptCinema",
              font=font_big, fill=ACCENT, anchor="mm")

    draw.text((WIDTH // 2, HEIGHT // 2),
              "Turning Code into Cinema",
              font=font_med, fill=TEXT_COLOR, anchor="mm")

    draw.text((WIDTH // 2, HEIGHT // 2 + 50),
              d["url"],
              font=font_sm, fill=DIM_COLOR, anchor="mm")

    draw.text((WIDTH // 2, HEIGHT // 2 + 90),
              f"Generated for: {d['full_name']}",
              font=font_tag, fill=ACCENT2, anchor="mm")

    arr = np.array(img).astype(np.float32)
    arr = (arr * alpha).astype(np.uint8)
    return arr


# ── Scene dispatch ────────────────────────────────────────────────────────────
_RENDERERS = {
    "intro": _render_intro,
    "languages": _render_languages,
    "filetree": _render_filetree,
    "code": _render_code,
    "commits": _render_commits,
    "stats": _render_stats,
    "outro": _render_outro,
}


def _scene_to_clip(scene: Scene) -> VideoClip:
    renderer = _RENDERERS[scene.scene_type]

    def make_frame(t: float) -> np.ndarray:
        return renderer(scene, t)

    return VideoClip(make_frame, duration=scene.duration)


# ── Public API ────────────────────────────────────────────────────────────────
def render_video(
    scenes: list[Scene],
    output_path: str,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> str:
    """
    Render all scenes into a single .mp4 file.

    Args:
        scenes: List of Scene objects
        output_path: Path where the .mp4 will be written
        progress_callback: Optional callback(scene_name, percent) called per scene

    Returns:
        Absolute path to the generated .mp4
    """
    clips = []
    total = len(scenes)

    for i, scene in enumerate(scenes):
        if progress_callback:
            pct = int((i / total) * 90)
            progress_callback(scene.name, pct)

        clip = _scene_to_clip(scene)
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")

    if progress_callback:
        progress_callback("Encoding video…", 90)

    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio=False,
        logger=None,
        preset="ultrafast",
    )

    if progress_callback:
        progress_callback("Done", 100)

    return os.path.abspath(output_path)
