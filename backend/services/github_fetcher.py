"""
GitHub API fetcher — retrieves all repo data needed for scene generation.
"""
import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from github import Github, GithubException

load_dotenv()


@dataclass
class CommitInfo:
    sha: str
    message: str
    author: str
    date: str


@dataclass
class RepoData:
    name: str
    full_name: str
    description: str
    owner_login: str
    owner_avatar_url: str
    stars: int
    forks: int
    open_issues: int
    watchers: int
    language: str
    languages: dict  # {"Python": 12345, "JavaScript": 6789}
    topics: list[str]
    created_at: str
    updated_at: str
    file_tree: list[str]          # Top-level paths (limited)
    top_code_file: Optional[str]  # Filename of the best code file to show
    top_code_content: Optional[str]  # File content (first 50 lines)
    commits: list[CommitInfo]     # Recent 10 commits
    contributors_count: int


def _get_github_client() -> Github:
    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        return Github(token)
    return Github()


def _extract_file_tree(repo, max_items: int = 40) -> list[str]:
    """Return a flat list of file/dir paths from the repo root, up to max_items."""
    try:
        contents = repo.get_contents("")
        tree: list[str] = []
        dirs = []
        files = []

        for item in contents:
            if item.type == "dir":
                dirs.append(f"📁 {item.name}/")
            else:
                files.append(f"📄 {item.name}")

        tree = dirs + files
        return tree[:max_items]
    except Exception:
        return []


_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".cs", ".rb", ".php", ".swift", ".kt", ".scala",
    ".r", ".sh", ".bash", ".sql", ".vue", ".svelte",
}

_SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", ".lock",
    "requirements.txt", "Pipfile.lock",
}


def _find_best_code_file(repo) -> tuple[Optional[str], Optional[str]]:
    """Find the best code file to showcase (most interesting, non-trivial)."""
    try:
        contents = repo.get_contents("")
        candidates = []
        for item in contents:
            if item.type == "file":
                ext = os.path.splitext(item.name)[1].lower()
                if ext in _CODE_EXTENSIONS and item.name not in _SKIP_FILES:
                    candidates.append(item)

        if not candidates:
            # Try one level deep
            for item in contents:
                if item.type == "dir":
                    try:
                        sub = repo.get_contents(item.path)
                        for sub_item in sub:
                            if sub_item.type == "file":
                                ext = os.path.splitext(sub_item.name)[1].lower()
                                if ext in _CODE_EXTENSIONS:
                                    candidates.append(sub_item)
                    except Exception:
                        pass

        if not candidates:
            return None, None

        # Prefer larger files (more interesting to show)
        candidates.sort(key=lambda x: x.size, reverse=True)
        best = candidates[0]
        content = best.decoded_content.decode("utf-8", errors="replace")
        # Limit to first 50 lines
        lines = content.splitlines()[:50]
        return best.path, "\n".join(lines)
    except Exception:
        return None, None


def fetch_repo_data(repo_url: str) -> RepoData:
    """
    Fetch all required data for a GitHub repo URL.
    Supports formats:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - github.com/owner/repo
    """
    # Parse owner/repo from URL
    url = repo_url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.split("github.com/")
    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub URL: {repo_url}")
    repo_path = parts[1].strip("/")

    g = _get_github_client()
    try:
        repo = g.get_repo(repo_path)
    except GithubException as e:
        raise ValueError(f"Cannot access repo '{repo_path}': {e.data.get('message', str(e))}")

    # Languages
    try:
        languages = repo.get_languages()
    except Exception:
        languages = {}

    # File tree
    file_tree = _extract_file_tree(repo)

    # Best code file
    top_file_path, top_file_content = _find_best_code_file(repo)

    # Recent commits
    commits: list[CommitInfo] = []
    try:
        for commit in repo.get_commits()[:10]:
            commits.append(
                CommitInfo(
                    sha=commit.sha[:7],
                    message=commit.commit.message.splitlines()[0][:80],
                    author=commit.commit.author.name,
                    date=commit.commit.author.date.strftime("%Y-%m-%d"),
                )
            )
    except Exception:
        pass

    # Contributors count
    try:
        contributors_count = repo.get_contributors().totalCount
    except Exception:
        contributors_count = 0

    return RepoData(
        name=repo.name,
        full_name=repo.full_name,
        description=repo.description or "No description provided.",
        owner_login=repo.owner.login,
        owner_avatar_url=repo.owner.avatar_url,
        stars=repo.stargazers_count,
        forks=repo.forks_count,
        open_issues=repo.open_issues_count,
        watchers=repo.watchers_count,
        language=repo.language or "Unknown",
        languages=languages,
        topics=repo.get_topics(),
        created_at=repo.created_at.strftime("%B %Y"),
        updated_at=repo.updated_at.strftime("%Y-%m-%d"),
        file_tree=file_tree,
        top_code_file=top_file_path,
        top_code_content=top_file_content,
        commits=commits,
        contributors_count=contributors_count,
    )
