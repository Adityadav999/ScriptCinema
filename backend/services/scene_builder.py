"""
Scene builder — converts raw RepoData into a list of Scene objects
that the video renderer uses to generate frames.
"""
from dataclasses import dataclass, field
from typing import Any

from services.github_fetcher import RepoData


@dataclass
class Scene:
    name: str            # Human-readable scene name shown in progress
    duration: float      # Scene duration in seconds
    scene_type: str      # "intro" | "languages" | "filetree" | "code" | "commits" | "stats" | "outro"
    data: dict[str, Any] = field(default_factory=dict)


def build_scenes(repo: RepoData) -> list[Scene]:
    """
    Build an ordered list of cinematic scenes from repo data.
    """
    scenes: list[Scene] = []

    # ── 1. Intro Title Card ──────────────────────────────────────────────────
    scenes.append(
        Scene(
            name="Intro Title Card",
            duration=4.0,
            scene_type="intro",
            data={
                "repo_name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "owner": repo.owner_login,
                "language": repo.language,
                "created_at": repo.created_at,
                "topics": repo.topics[:5],
            },
        )
    )

    # ── 2. Language Breakdown ────────────────────────────────────────────────
    if repo.languages:
        total = sum(repo.languages.values())
        lang_data = [
            {"name": lang, "bytes": val, "pct": round(val / total * 100, 1)}
            for lang, val in sorted(repo.languages.items(), key=lambda x: x[1], reverse=True)
        ][:8]  # Max 8 languages
        scenes.append(
            Scene(
                name="Language Breakdown",
                duration=4.5,
                scene_type="languages",
                data={"languages": lang_data},
            )
        )

    # ── 3. File Tree Explorer ────────────────────────────────────────────────
    if repo.file_tree:
        scenes.append(
            Scene(
                name="File Tree Explorer",
                duration=5.0,
                scene_type="filetree",
                data={
                    "repo_name": repo.name,
                    "tree": repo.file_tree[:30],
                },
            )
        )

    # ── 4. Code Showcase ─────────────────────────────────────────────────────
    if repo.top_code_content:
        scenes.append(
            Scene(
                name="Code Showcase",
                duration=6.0,
                scene_type="code",
                data={
                    "filename": repo.top_code_file or "main",
                    "content": repo.top_code_content,
                    "language": repo.language,
                },
            )
        )

    # ── 5. Commit History Timeline ───────────────────────────────────────────
    if repo.commits:
        scenes.append(
            Scene(
                name="Commit History",
                duration=5.0,
                scene_type="commits",
                data={
                    "commits": [
                        {
                            "sha": c.sha,
                            "message": c.message,
                            "author": c.author,
                            "date": c.date,
                        }
                        for c in repo.commits[:8]
                    ]
                },
            )
        )

    # ── 6. Stats Card ────────────────────────────────────────────────────────
    scenes.append(
        Scene(
            name="Repository Stats",
            duration=4.0,
            scene_type="stats",
            data={
                "stars": repo.stars,
                "forks": repo.forks,
                "issues": repo.open_issues,
                "watchers": repo.watchers,
                "contributors": repo.contributors_count,
                "updated_at": repo.updated_at,
            },
        )
    )

    # ── 7. Outro ─────────────────────────────────────────────────────────────
    scenes.append(
        Scene(
            name="Outro",
            duration=3.0,
            scene_type="outro",
            data={
                "full_name": repo.full_name,
                "url": f"https://github.com/{repo.full_name}",
            },
        )
    )

    return scenes
