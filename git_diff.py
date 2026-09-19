import subprocess
from pathlib import Path

from agent import AgentError

SOURCE_GLOBS = (
    ":(glob)**/*.py",
    ":(glob)**/*.java",
    ":(glob)**/*.c",
    ":(glob)**/*.h",
    ":(glob)**/*.cpp",
    ":(glob)**/*.cc",
    ":(glob)**/*.cxx",
    ":(glob)**/*.hpp",
    ":(glob)**/*.js",
    ":(glob)**/*.ts",
)


def collect_git_diff(
    repo: str = ".",
    revision: str = "HEAD",
    staged: bool = False,
    pathspecs: list[str] | None = None,
) -> tuple[str, str]:
    """Return (unified_diff, source_label) from a local git repo."""
    root = Path(repo).expanduser().resolve()
    if not root.exists():
        raise AgentError(f"Repo path not found: {root}")

    git_dir = root / ".git"
    if not git_dir.exists():
        raise AgentError(f"{root} is not a git repository.")

    command = ["git", "-C", str(root), "diff", "--no-ext-diff", "--no-color"]
    source = (
        f"git diff --staged ({root.name})"
        if staged
        else f"git diff {revision} ({root.name})"
    )
    if staged:
        command.append("--cached")
    else:
        command.append(revision)
    command.append("--")
    command.extend(pathspecs if pathspecs else list(SOURCE_GLOBS))

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise AgentError("git is not installed or not on PATH.") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise AgentError(detail or f"git diff failed ({completed.returncode}).")

    return completed.stdout, source
