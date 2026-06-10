"""Resolve a repository's DECLARED Python version and map it to an interpreter.

Building every repo under one fixed interpreter (we used 3.12) confounds the
reproducibility signal: old pinned deps have no 3.12 wheels and old sdists fail
to build on 3.12 (removed `imp`/`zipimporter`/`pkg_resources`). To make a
resolution/build failure attributable to the repo rather than our setup, we
build each repo against the Python version it declares.

Requires a one-time interpreter ladder on the cluster, e.g.:
  for v in 3.8 3.9 3.10 3.11 3.12; do
    /opt/miniconda3/bin/conda create -y -p ~/pys/py${v//./} python=$v
  done
If the ladder is absent, choose_interpreter() falls back to the current
interpreter and flags ladder_available=False (graceful degradation).
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

SUPPORTED = ["3.8", "3.9", "3.10", "3.11", "3.12"]
PY_LADDER_BASE = os.getenv("SRAF_PY_LADDER", str(Path.home() / "pys"))
DEFAULT_PY = os.getenv("SRAF_DEFAULT_PY", "3.10")   # for repos that declare none


def _tup(v: str) -> tuple[int, int]:
    a, b = v.split(".")[:2]
    return (int(a), int(b))


def _dist(a: str, b: str) -> int:
    ta, tb = _tup(a), _tup(b)
    return abs((ta[0] - tb[0]) * 100 + (ta[1] - tb[1]))


def _norm(v: str) -> str | None:
    """Clamp a declared version string to the nearest SUPPORTED rung."""
    try:
        _tup(v)
    except (ValueError, IndexError):
        return None
    return min(SUPPORTED, key=lambda s: _dist(s, v))


def _from_specifier(spec: str) -> str | None:
    """Pick the highest SUPPORTED version satisfying a python_requires string."""
    cons = re.findall(r"(>=|<=|==|~=|<|>)\s*([23]\.\d{1,2})", spec)
    def ok(v: str) -> bool:
        f = _tup(v)
        for op, bound in cons:
            b = _tup(bound)
            if op in (">=", "~=") and not f >= b: return False
            if op == ">" and not f > b: return False
            if op == "<=" and not f <= b: return False
            if op == "<" and not f < b: return False
            if op == "==" and not f == b: return False
        return True
    cand = [s for s in SUPPORTED if ok(s)]
    return max(cand, key=_tup) if cand else None


def resolve_python_version(clone_dir: str, artifacts: dict) -> tuple[str | None, str]:
    """Return (version|None, source) from the repo's declared metadata."""
    root = Path(clone_dir)
    by = artifacts.get("by_type", {}) or {}

    # 1. conda environment.yml — `python=3.9` / `python>=3.8`
    if "conda" in by:
        f = root / by["conda"]
        if f.exists():
            m = re.search(r"python\s*[=>]=?\s*([23]\.\d{1,2})", f.read_text(errors="ignore"))
            if m:
                return _norm(m.group(1)), "conda"

    # 2. .python-version (pyenv)
    f = root / ".python-version"
    if f.exists():
        m = re.search(r"([23]\.\d{1,2})", f.read_text(errors="ignore"))
        if m:
            return _norm(m.group(1)), ".python-version"

    # 3. runtime.txt
    f = root / "runtime.txt"
    if f.exists():
        m = re.search(r"python-?\s*([23]\.\d{1,2})", f.read_text(errors="ignore"), re.I)
        if m:
            return _norm(m.group(1)), "runtime.txt"

    # 4. Dockerfile — PYTHON_VERSION arg/env or `FROM python:3.9`
    if "docker" in by:
        f = root / by["docker"]
        if f.exists():
            t = f.read_text(errors="ignore")
            m = (re.search(r"FROM\s+python:([23]\.\d{1,2})", t, re.I)
                 or re.search(r"PYTHON_VERSION[=:\s\"']*([23]\.\d{1,2})", t, re.I))
            if m:
                return _norm(m.group(1)), "dockerfile"

    # 5. python_requires / requires-python in setup.py / pyproject / setup.cfg
    for name in ("setup.py", "pyproject.toml", "setup.cfg"):
        f = root / name
        if f.exists():
            t = f.read_text(errors="ignore")
            m = (re.search(r"python_requires\s*=\s*[\"']([^\"']+)[\"']", t)
                 or re.search(r"requires-python\s*=\s*[\"']([^\"']+)[\"']", t))
            if m:
                v = _from_specifier(m.group(1))
                if v:
                    return v, "python_requires"

    return None, "default"


def _interp(ver: str) -> str | None:
    p = Path(PY_LADDER_BASE) / f"py{ver.replace('.', '')}" / "bin" / "python"
    return str(p) if p.exists() else None


def choose_interpreter(version: str | None) -> tuple[str, str, bool]:
    """Return (python_path, version_used, ladder_available)."""
    target = version or DEFAULT_PY
    p = _interp(target)
    if p:
        return p, target, True
    # nearest available rung in the ladder
    for v in sorted(SUPPORTED, key=lambda x: _dist(x, target)):
        q = _interp(v)
        if q:
            return q, v, True
    # graceful fallback: whatever interpreter is running this
    return sys.executable, f"{sys.version_info.major}.{sys.version_info.minor}", False
