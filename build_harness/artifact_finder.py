"""Recursive, priority-ranked artifact search.

The lifter's parsers only check a fixed candidate list at a repo's root
(Dockerfile, docker/Dockerfile, ...). Real repos place artifacts deeper:
the Block-1 finding was that huggingface/transformers keeps its Dockerfile
under docker/transformers-pytorch-gpu/. This module does the recursive search
with priority rules (root > top-level subdir > deeper) so the harness feeds
the right directory to each parser — and records *where* artifacts were found,
which is itself a reportable real-world result.
"""
from __future__ import annotations
from pathlib import Path

# Filename patterns grouped by the parser that consumes them.
ARTIFACT_PATTERNS = {
    "docker": ["Dockerfile", "Dockerfile.*", "*.Dockerfile"],
    "conda":  ["environment.yml", "environment.yaml", "conda.yml", "conda.yaml"],
    "pip":    ["requirements.txt", "requirements-*.txt", "requirements/*.txt"],
    "setup":  ["setup.py", "pyproject.toml", "setup.cfg"],
    "r":      ["renv.lock", "DESCRIPTION"],          # out-of-distribution set
}

# Directories never worth descending into.
SKIP_DIRS = {
    ".git", ".github", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "site-packages", ".mypy_cache", ".pytest_cache",
    "build", "dist", ".tox", ".idea", "docs/_build",
}

MAX_DEPTH = 4  # root is depth 0; deeper than this is almost always vendored

# Path hints that mark an artifact as auxiliary (docs/tests/examples) — used to
# break depth ties in favour of a real runtime spec.
DEPRIORITIZE = ("doc", "test", "example", "benchmark", "tutorial", "sample")

# The canonical filename for each type. A variant like requirements-1bit-mpi.txt
# must never beat the real requirements.txt at the same depth.
CANONICAL = {
    "docker": {"dockerfile"},
    "conda":  {"environment.yml", "environment.yaml"},
    "pip":    {"requirements.txt"},
    "setup":  {"pyproject.toml", "setup.py"},
    "r":      {"renv.lock"},
}


def _matches(name: str, pattern: str) -> bool:
    return Path(name).match(pattern)


def _rank(a: dict) -> tuple:
    """Lower is better: shallow → canonical → non-auxiliary → path order."""
    name = Path(a["rel_path"]).name.lower()
    non_canon = 0 if name in CANONICAL.get(a["type"], set()) else 1
    aux = 1 if any(k in a["rel_path"].lower() for k in DEPRIORITIZE) else 0
    return (a["depth"], non_canon, aux, a["rel_path"])


def find_artifacts(repo_dir: str) -> dict:
    """Walk a repo and rank artifacts by location priority.

    Returns:
      {
        "all":         [ {type, rel_path, depth}, ... ],   # everything found
        "by_type":     { "docker": <best rel_path>, ... }, # highest-priority each
        "primary_dir": <abs path of the best directory to lift from>,
        "depth_note":  "root" | "subdir" | "deep" | "none",
      }
    Lower depth wins; within a depth, types are taken in ARTIFACT_PATTERNS order.
    """
    root = Path(repo_dir).resolve()
    found: list[dict] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # depth = number of path components below the repo root
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        depth = len(rel.parts) - 1
        if depth > MAX_DEPTH:
            continue
        for atype, patterns in ARTIFACT_PATTERNS.items():
            if any(_matches(path.name, p) for p in patterns):
                found.append({"type": atype, "rel_path": str(rel), "depth": depth})
                break

    # Best artifact per type: shallow + non-auxiliary wins (see _rank).
    by_type: dict[str, str] = {}
    best_of: dict[str, dict] = {}
    for atype in ARTIFACT_PATTERNS:
        candidates = [a for a in found if a["type"] == atype]
        if candidates:
            best = min(candidates, key=_rank)
            by_type[atype] = best["rel_path"]
            best_of[atype] = best

    # Primary directory to lift from: the container/env spec with the best rank
    # (docker > conda > pip > setup), since it anchors the ComputingEnvironment.
    primary_dir = root
    depth_note = "none"
    for atype in ("docker", "conda", "pip", "setup"):
        if atype in best_of:
            primary_dir = (root / best_of[atype]["rel_path"]).parent
            d = best_of[atype]["depth"]
            depth_note = "root" if d == 0 else ("subdir" if d == 1 else "deep")
            break

    return {
        "all": found,
        "by_type": by_type,
        "primary_dir": str(primary_dir),
        "depth_note": depth_note,
    }
