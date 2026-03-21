# lifter/parsers/pip_parser.py
"""
Parses pip requirements.txt files into a normalised dict
ready for RDIP mapping.
"""

import re
from pathlib import Path


def parse_requirements(filepath: str) -> dict:
    """
    Parse a pip requirements.txt file.
    Handles pinned (==), minimum (>=), range (>=x,<y),
    and URL-based dependencies.
    Returns a normalised dict.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Requirements file not found: {filepath}")

    content = path.read_text(encoding="utf-8", errors="ignore")
    lines   = content.splitlines()

    dependencies     = []
    constraints_files = []
    index_urls       = []

    for raw_line in lines:
        line = raw_line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Index URL directives
        if line.startswith(("-i ", "--index-url", "--extra-index-url")):
            index_urls.append(line)
            continue

        # Constraint file references
        if line.startswith(("-c ", "--constraint")):
            constraints_files.append(line)
            continue

        # Recursive requirements file — skip
        if line.startswith(("-r ", "--requirement")):
            continue

        # Options like --no-binary — skip
        if line.startswith("-"):
            continue

        name, version, dep_type = _parse_requirement_line(line)
        if name:
            dependencies.append({
                "name":    name,
                "version": version or "unspecified",
                "type":    dep_type,
            })

    return {
        "source":       "pip",
        "dependencies": dependencies,
        "spec_type":    "pip-requirements",
        "spec_uri":     str(path.resolve()),
    }


def _parse_requirement_line(line: str) -> tuple[str, str | None, str]:
    """
    Parse a single pip requirement line.
    Returns (name, version, type).
    type is one of: 'pip', 'url', 'editable'
    """
    # Editable installs
    if line.startswith("-e "):
        url = line[3:].strip()
        name = url.split("/")[-1].split(".git")[0].split("@")[0]
        return name.lower(), None, "editable"

    # URL-based installs
    if line.startswith(("git+", "http://", "https://", "ftp://")):
        name = line.split("/")[-1].split(".git")[0].split("@")[0]
        name = re.sub(r"[^a-z0-9\-_]", "", name.lower())
        return name or "unknown_url_dep", None, "url"

    # Strip inline comments
    line = line.split(" #")[0].strip()

    # Strip extras: package[extra] → package
    line_clean = re.sub(r"\[.*?\]", "", line)

    # Match name and version constraint
    m = re.match(
        r"^([A-Za-z0-9_\-\.]+)\s*([=<>!~]+.*)?$",
        line_clean.strip()
    )
    if not m:
        return "", None, "pip"

    name = m.group(1).strip().lower().replace("-", "_")

    version_str = m.group(2).strip() if m.group(2) else None
    version     = None

    if version_str:
        # Prefer pinned versions (==)
        pinned = re.search(r"==\s*([\d.]+\w*)", version_str)
        if pinned:
            version = pinned.group(1)
        else:
            # Take the first version bound
            any_bound = re.search(r"[>=!<~]+\s*([\d.]+\w*)", version_str)
            if any_bound:
                version = any_bound.group(1)

    return name, version, "pip"


def from_repo(repo_dir: str) -> dict | None:
    """
    Auto-detect and parse the best available requirements file in a repo.
    Returns parsed dict or None if nothing found.
    Prefers the most specific file.
    """
    repo_path = Path(repo_dir)

    candidates = [
        repo_path / "requirements.txt",
        repo_path / "requirements" / "requirements.txt",
        repo_path / "requirements" / "base.txt",
        repo_path / "requirements" / "main.txt",
        repo_path / "requirements-base.txt",
        repo_path / "requirements-core.txt",
    ]

    for candidate in candidates:
        if candidate.exists():
            print(f"[PipParser] Found {candidate.relative_to(repo_path)}")
            return parse_requirements(str(candidate))

    return None
