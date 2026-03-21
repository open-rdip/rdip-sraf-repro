# lifter/parsers/conda_parser.py
"""
Parses Conda environment files (environment.yml / environment.yaml)
into a normalised dict ready for RDIP mapping.
"""

import yaml
import re
from pathlib import Path


def parse_conda_env(filepath: str) -> dict:
    """
    Parse a conda environment.yml file.
    Returns a normalised dict with all dependencies extracted.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Conda env file not found: {filepath}")

    with open(path, encoding="utf-8") as f:
        env = yaml.safe_load(f)

    if not env:
        raise ValueError(f"Empty or invalid conda env file: {filepath}")

    dependencies  = []
    python_version = None
    pip_deps       = []

    for dep in env.get("dependencies", []):

        if isinstance(dep, str):
            name, version, build = _parse_conda_dep(dep)

            # Track Python version separately
            if name.lower() == "python" and version:
                python_version = version

            dependencies.append({
                "name":    name,
                "version": version or "unspecified",
                "build":   build,
                "type":    "conda",
            })

        elif isinstance(dep, dict) and "pip" in dep:
            for pip_dep in dep["pip"]:
                name, version = _parse_pip_dep(pip_dep)
                pip_deps.append({
                    "name":    name,
                    "version": version or "unspecified",
                    "type":    "pip",
                })

    return {
        "source":          "conda",
        "env_name":        env.get("name", "unknown"),
        "python_version":  python_version,
        "channels":        env.get("channels", []),
        "dependencies":    dependencies,
        "pip_dependencies":pip_deps,
        "spec_type":       "conda",
        "spec_uri":        str(path.resolve()),
    }


def _parse_conda_dep(dep_str: str) -> tuple[str, str | None, str | None]:
    """
    Parse a conda dependency string.
    Handles formats:
      python=3.10.2
      numpy=1.24.3=py310h...  (with build string)
      pytorch::torch>=2.0
      scipy  (no version)
    Returns (name, version, build_string)
    """
    dep_str = dep_str.strip()

    # Handle channel::package notation
    if "::" in dep_str:
        dep_str = dep_str.split("::", 1)[1]

    # Split on = separators
    parts = re.split(r"[=<>!]+", dep_str, maxsplit=2)
    name  = parts[0].strip()

    # Extract operator + version
    version_match = re.search(r"[=<>!]+(.+?)(?:=.+)?$", dep_str)
    version = None
    build   = None

    if version_match:
        rest = dep_str[len(name):]
        # If there are two = signs: name=version=build
        eq_parts = dep_str.split("=")
        if len(eq_parts) >= 3:
            version = eq_parts[1].strip()
            build   = eq_parts[2].strip() if len(eq_parts) > 2 else None
        elif len(eq_parts) == 2:
            version = eq_parts[1].strip()
        else:
            # >=, <=, !=, etc.
            m = re.search(r"([<>=!]+)([\d.]+\w*)", rest)
            if m:
                version = m.group(2)

    return name.lower(), version, build


def _parse_pip_dep(dep_str: str) -> tuple[str, str | None]:
    """
    Parse a pip dependency string.
    Handles: torch==2.1.0, numpy>=1.24, requests, git+https://...
    Returns (name, version)
    """
    dep_str = dep_str.strip()

    # Skip git/url dependencies
    if dep_str.startswith(("git+", "http://", "https://", "-e")):
        name = dep_str.split("/")[-1].split(".git")[0].split("@")[0]
        return name.lower(), None

    # Handle extras: package[extra]==version
    dep_clean = re.sub(r"\[.*?\]", "", dep_str)

    # Split on version operators
    m = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([=<>!]+)\s*([\d.]+\w*)?", dep_clean)
    if m:
        name    = m.group(1).strip().lower()
        version = m.group(3).strip() if m.group(3) else None
        return name, version

    return dep_clean.strip().lower(), None


def from_repo(repo_dir: str) -> dict | None:
    """
    Auto-detect and parse the best available conda env file in a repo.
    Returns parsed dict or None if no conda file found.
    """
    from pathlib import Path
    repo_path = Path(repo_dir)

    candidates = [
        repo_path / "environment.yml",
        repo_path / "environment.yaml",
        repo_path / "conda.yml",
        repo_path / "conda" / "environment.yml",
        repo_path / "docker" / "environment.yml",
        repo_path / "env" / "environment.yml",
    ]

    for candidate in candidates:
        if candidate.exists():
            print(f"[CondaParser] Found {candidate.relative_to(repo_path)}")
            return parse_conda_env(str(candidate))

    return None
