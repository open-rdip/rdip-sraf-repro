"""Repo-level metadata recoverable from the clone — no LLM required.

Extracts the three FAIR-R signals that live in the repository itself:
commit hash (git), software license (LICENSE file → SPDX), and an identifier
(paper/repo URL). Everything else FAIR-R checks for (seeds, eval results,
methods, dataset access) needs the paper PDF / RAG path.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

LICENSE_FILENAMES = [
    "LICENSE", "LICENSE.txt", "LICENSE.md", "LICENSE.rst",
    "COPYING", "COPYING.txt", "LICENCE", "LICENCE.txt",
]

# Ordered so that more specific signatures are tested before subsets
# (e.g. BSD-3 before BSD-2, GPL-3 before GPL-2).
SPDX_SIGNATURES = [
    ("Apache-2.0",   ["apache license", "version 2.0"]),
    ("GPL-3.0",      ["gnu general public license", "version 3"]),
    ("GPL-2.0",      ["gnu general public license", "version 2"]),
    ("LGPL-3.0",     ["gnu lesser general public license", "version 3"]),
    ("MPL-2.0",      ["mozilla public license", "version 2.0"]),
    ("BSD-3-Clause", ["redistribution and use", "neither the name"]),
    ("BSD-2-Clause", ["redistribution and use"]),
    ("MIT",          ["permission is hereby granted, free of charge"]),
    ("ISC",          ["isc license"]),
    ("Unlicense",    ["this is free and unencumbered software released into the public domain"]),
]


def _detect_license(clone_dir: str) -> str | None:
    root = Path(clone_dir)
    for name in LICENSE_FILENAMES:
        p = root / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="ignore")[:4000].lower()
            for spdx, sigs in SPDX_SIGNATURES:
                if all(s in text for s in sigs):
                    return spdx
            return "LicenseRef-Custom"   # license present but unrecognised
    return None


def _commit_hash(clone_dir: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", clone_dir, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def extract_repo_metadata(clone_dir: str, repo_url: str,
                          identifier: str | None = None) -> dict:
    """Return {identifier, commit_hash, software_license}.

    `identifier` defaults to the repo URL; pass a DOI / arXiv URL if available
    for a stronger persistent identifier.
    """
    return {
        "identifier": identifier or repo_url,
        "commit_hash": _commit_hash(clone_dir),
        "software_license": _detect_license(clone_dir),
    }
