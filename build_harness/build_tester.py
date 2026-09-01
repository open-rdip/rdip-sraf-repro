"""Containerless build test — the reproducibility success/failure signal.

No containers on the compute nodes, so each repo's environment is constructed
in an ephemeral virtualenv inside node-local scratch and torn down with the
clone. "Build succeeds" here means the declared Python environment installs
cleanly — the Type A (environment constructs) vs Type B (it doesn't) signal
behind RQ1. System-level deps (apt, CUDA) are NOT isolated; that limitation is
recorded honestly in the outcome rather than hidden.
"""
from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path


def _run(cmd: list[str], cwd: str, timeout: int, log: list[str]) -> tuple[int, str]:
    """Run a command, capture combined output, append a tail to `log`."""
    try:
        p = subprocess.run(
            cmd, cwd=cwd, timeout=timeout,
            capture_output=True, text=True,
        )
        out = (p.stdout or "") + (p.stderr or "")
        log.append(f"$ {' '.join(cmd)}\n{out[-2000:]}")
        return p.returncode, out
    except subprocess.TimeoutExpired:
        log.append(f"$ {' '.join(cmd)}\n[TIMEOUT after {timeout}s]")
        return 124, "timeout"
    except Exception as e:  # noqa: BLE001
        log.append(f"$ {' '.join(cmd)}\n[ERROR {e}]")
        return 1, str(e)


def run_build_test(repo_dir: str, artifacts: dict, scratch_dir: str,
                   timeout: int = 1800, base_python: str | None = None,
                   extra_index: list | None = None) -> dict:
    """Two-level reproducibility outcome for the declared Python environment.

    Tier 1 — RESOLUTION: does the declared dependency set resolve into a
             consistent install plan? (pip --dry-run) A failure here means the
             spec itself is internally broken / unsatisfiable.
    Tier 2 — BUILD:      does it actually install into a clean venv, including
             any compiled extensions? A pass here is full environment
             reconstruction.

    Returns:
      {
        "attempted":       bool,
        "resolve_success": bool | None,   # Tier 1
        "build_success":   bool,          # Tier 2 (the headline outcome)
        "method":          "pip-requirements" | "pip-setup" | "none",
        "stage_failed":    str | None,    # venv-create|resolve|build-install|*-timeout
        "duration_s":      float,
        "log_tail":        str,
        "notes":           str,
      }
    """
    t0 = time.time()
    log: list[str] = []
    by_type = artifacts["by_type"]
    primary_dir = artifacts["primary_dir"]

    # Decide install target from what was found.
    setup_dir = None
    if "setup" in by_type:
        d = (Path(repo_dir) / by_type["setup"]).parent
        if (d / "setup.py").exists() or (d / "pyproject.toml").exists():
            setup_dir = str(d)   # setup.cfg alone is not pip-installable

    if "pip" in by_type:
        method = "pip-requirements"
        target = ["-r", str(Path(repo_dir) / by_type["pip"])]
        cwd = repo_dir
    elif setup_dir:
        method = "pip-setup"
        target = ["."]
        cwd = setup_dir
    else:
        return {
            "attempted": False, "resolve_success": None, "build_success": False,
            "method": "none", "stage_failed": None,
            "duration_s": round(time.time() - t0, 1), "log_tail": "",
            "notes": "No installable pip/setup artifact "
                     "(requirements / setup.py / pyproject absent).",
        }

    venv_dir = Path(scratch_dir) / "venv"
    notes = ""
    if "conda" in by_type:
        notes = "environment.yml present but built via pip venv (conda build deferred)."

    # Build the venv with the repo's DECLARED Python (base_python), not ours.
    py = base_python or sys.executable
    # PyTorch/CUDA wheels (e.g. torch==x+cuYYY) live on the PyTorch index.
    idx = []
    for u in (extra_index or []):
        idx += ["--extra-index-url", u]

    # 0. create venv
    rc, _ = _run([py, "-m", "venv", str(venv_dir)],
                 cwd=scratch_dir, timeout=120, log=log)
    if rc != 0:
        return _result(method, None, False, "venv-create", t0, log, notes)

    pip = str(venv_dir / "bin" / "pip")
    # best-effort tooling upgrade (don't gate the outcome on it)
    _run([pip, "install", "--upgrade", "pip", "setuptools", "wheel"],
         cwd=scratch_dir, timeout=300, log=log)

    # Tier 1 — RESOLUTION (dry-run: resolve the dependency graph, install nothing)
    rc, _ = _run([pip, "install", "--dry-run", "--ignore-installed"] + idx + target,
                 cwd=cwd, timeout=min(timeout, 600), log=log)
    if rc == 124:
        return _result(method, False, False, "resolve-timeout", t0, log, notes)
    if rc != 0:
        return _result(method, False, False, "resolve", t0, log, notes)

    # Tier 2 — BUILD (actually install into the venv)
    rc, _ = _run([pip, "install"] + idx + target, cwd=cwd, timeout=timeout, log=log)
    if rc == 124:
        return _result(method, True, False, "build-timeout", t0, log, notes)
    if rc != 0:
        return _result(method, True, False, "build-install", t0, log, notes)

    return _result(method, True, True, None, t0, log, notes)


def _result(method, resolve_success, build_success, stage_failed, t0, log, notes):
    return {
        "attempted": True,
        "resolve_success": resolve_success,
        "build_success": build_success,
        "method": method,
        "stage_failed": stage_failed,
        "duration_s": round(time.time() - t0, 1),
        "log_tail": "\n".join(log)[-4000:],
        "notes": notes,
    }
