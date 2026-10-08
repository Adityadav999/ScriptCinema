"""
browser_actor.py — Playwright browser automation with built-in video recording.

Opens the running project in a headless Chromium browser, navigates through
pages, interacts with forms, and records the entire session as a .webm file.
"""
import time
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import sync_playwright, Page, BrowserContext


# ── Sample data for form filling ─────────────────────────────────────────────
_FORM_DATA = {
    "email":    "demo@scriptcinema.dev",
    "name":     "ScriptCinema",
    "username": "scriptcinema_demo",
    "search":   "demo",
    "query":    "cinematic video",
    "text":     "Hello from ScriptCinema!",
    "message":  "This is a demo message from ScriptCinema 🎬",
    "phone":    "9876543210",
    "password": "Demo@1234",
    "url":      "https://github.com/Adityadav999/ScriptCinema",
}


# ── Main recording function ───────────────────────────────────────────────────
def record_session(
    port: int,
    output_dir: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Launch Playwright Chromium, navigate the app on localhost:<port>,
    interact with it, and return the path to the recorded .webm file.
    """

    def _progress(msg: str):
        if on_progress:
            on_progress(msg)

    base_url = f"http://localhost:{port}"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        context: BrowserContext = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=output_dir,
            record_video_size={"width": 1280, "height": 720},
            # Ignore HTTPS certificate errors on local dev servers
            ignore_https_errors=True,
        )

        page: Page = context.new_page()

        try:
            # ── Scene 1: Home page ────────────────────────────────────────
            _progress("Opening home page…")
            page.goto(base_url, timeout=30_000, wait_until="domcontentloaded")
            _wait(page, 2.0)

            # Slow cinematic scroll of the home page
            _progress("Scrolling home page…")
            _cinematic_scroll(page, steps=40, step_delay=0.08)
            _wait(page, 1.5)

            # Scroll back to top
            page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
            _wait(page, 1.0)

            # ── Scene 2: Navigate through nav links ───────────────────────
            _progress("Exploring navigation…")
            nav_links = _extract_nav_links(page, base_url)

            visited: set[str] = {base_url, base_url + "/"}
            scenes_visited = 0

            for href in nav_links:
                if scenes_visited >= 5:
                    break
                if href in visited:
                    continue
                visited.add(href)

                label = href.rstrip("/").split("/")[-1] or "page"
                _progress(f"Visiting /{label}…")

                try:
                    page.goto(href, timeout=15_000, wait_until="domcontentloaded")
                    _wait(page, 1.5)
                    _cinematic_scroll(page, steps=25, step_delay=0.07)
                    _wait(page, 1.0)
                    scenes_visited += 1
                except Exception:
                    continue

            # ── Scene 3: Back to home — try interactive elements ──────────
            _progress("Interacting with the app…")
            try:
                page.goto(base_url, timeout=15_000, wait_until="domcontentloaded")
                _wait(page, 1.0)
            except Exception:
                pass

            _fill_forms(page)
            _wait(page, 1.5)

            # ── Scene 4: Click buttons / CTAs ─────────────────────────────
            _progress("Clicking buttons…")
            _click_buttons(page)
            _wait(page, 2.0)

        except Exception:
            # Even a partial recording is valuable
            pass

        finally:
            context.close()
            browser.close()

    # Find the .webm file written by Playwright
    webm_files = sorted(
        Path(output_dir).glob("*.webm"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not webm_files:
        raise RuntimeError(
            "Playwright did not produce a video recording. "
            "Make sure the project server was reachable and Chromium is installed."
        )
    return str(webm_files[0])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wait(page: Page, seconds: float):
    """Wait without blocking Playwright's internal timers."""
    page.wait_for_timeout(int(seconds * 1000))


def _cinematic_scroll(page: Page, steps: int = 40, step_delay: float = 0.07):
    """Smoothly scroll from top to bottom of the page."""
    try:
        page.evaluate(f"""
            () => {{
                const total = Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight
                ) - window.innerHeight;
                const steps = {steps};
                let i = 0;
                const t = setInterval(() => {{
                    window.scrollBy(0, total / steps);
                    if (++i >= steps) clearInterval(t);
                }}, {int(step_delay * 1000)});
            }}
        """)
        page.wait_for_timeout(int(steps * step_delay * 1000) + 500)
    except Exception:
        pass


def _extract_nav_links(page: Page, base_url: str) -> list[str]:
    """
    Pull href values from nav/header anchor tags that are internal links.
    """
    try:
        raw = page.evaluate(
            """(base) => {
                const selectors = [
                    'nav a', 'header a', '[role="navigation"] a',
                    '.navbar a', '.nav a', '.menu a', '.sidebar a',
                    'aside a',
                ];
                const els = selectors.flatMap(s => [...document.querySelectorAll(s)]);
                return [...new Set(
                    els
                        .map(a => a.href.split('#')[0].split('?')[0])
                        .filter(h =>
                            h.startsWith(base) &&
                            h !== base &&
                            h !== base + '/'
                        )
                )].slice(0, 10);
            }""",
            base_url,
        )
        return raw or []
    except Exception:
        return []


def _fill_forms(page: Page):
    """Find visible text inputs and type sample data into them."""
    try:
        inputs = page.query_selector_all(
            "input:not([type=hidden]):not([type=submit]):not([type=checkbox])"
            ":not([type=radio]):not([type=file]):not([disabled]):not([readonly])"
        )
        for inp in inputs[:5]:
            try:
                if not inp.is_visible():
                    continue
                inp_type = (inp.get_attribute("type") or "text").lower()
                name = (
                    inp.get_attribute("name") or
                    inp.get_attribute("placeholder") or
                    inp.get_attribute("id") or
                    ""
                ).lower()

                # Pick the best matching sample value
                value = _FORM_DATA["text"]
                for key, val in _FORM_DATA.items():
                    if key in name or inp_type == key:
                        value = val
                        break

                inp.scroll_into_view_if_needed()
                inp.click()
                page.wait_for_timeout(200)
                inp.fill(value)
                page.wait_for_timeout(400)
            except Exception:
                continue
    except Exception:
        pass


def _click_buttons(page: Page):
    """Click visible CTA/primary buttons (skip form-submit buttons)."""
    try:
        buttons = page.query_selector_all(
            "button:not([type=submit]):not([disabled]), "
            "a[class*='btn']:not([disabled]), "
            "a[class*='button']:not([disabled])"
        )
        clicked = 0
        for btn in buttons[:4]:
            try:
                if not btn.is_visible():
                    continue
                text = (btn.inner_text() or "").strip().lower()
                # Skip dangerous / nav-back buttons
                if any(w in text for w in ["delete", "remove", "logout", "sign out", "cancel"]):
                    continue
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(800)
                clicked += 1
            except Exception:
                continue
    except Exception:
        pass
