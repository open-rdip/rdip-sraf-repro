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
                   timeout: int = 1800) -> dict:
    """Attempt to construct the repo's Python environment in a scratch venv.

    Returns:
      {
        "attempted":   bool,
        "success":     bool,
        "method":      "pip-requirements" | "pip-setup" | "none",
        "stage_failed": str | None,
        "duration_s":  float,
        "log_tail":    str,
        "notes":       str,
      }
    """
    t0 = time.time()
    log: list[str] = []
    by_type = artifacts["by_type"]
    primary_dir = artifacts["primary_dir"]

    # Decide install method from what was found.
    if "pip" in by_type:
        method = "pip-requirements"
        req_path = str(Path(repo_dir) / by_type["pip"])
        install_cmd_factory = lambda pip: [pip, "install", "-r", req_path]
        install_cwd = repo_dir
    elif "setup" in by_type:
        method = "pip-setup"
        install_cmd_factory = lambda pip: [pip, "install", "."]
        install_cwd = primary_dir
    else:
        return {
            "attempted": False, "success": False, "method": "none",
            "stage_failed": None, "duration_s": round(time.time() - t0, 1),
            "log_tail": "", "notes": "No pip/setup artifact to build from "
                                     "(docker/conda-only builds deferred).",
        }

    venv_dir = Path(scratch_dir) / "venv"
    notes = ""
    if "conda" in by_type:
        notes = "environment.yml present but built via pip venv (conda build deferred)."

    # 1. create venv
    rc, _ = _run([sys.executable, "-m", "venv", str(venv_dir)],
                 cwd=scratch_dir, timeout=120, log=log)
    if rc != 0:
        return _result(False, method, "venv-create", t0, log, notes)

    pip = str(venv_dir / "bin" / "pip")
    # 2. upgrade pip (best-effort, don't fail the build on this)
    _run([pip, "install", "--upgrade", "pip", "setuptools", "wheel"],
         cwd=scratch_dir, timeout=300, log=log)

    # 3. the actual install — this is the reproducibility signal
    rc, _ = _run(install_cmd_factory(pip), cwd=install_cwd, timeout=timeout, log=log)
    if rc == 124:
        return _result(False, method, "install-timeout", t0, log, notes)
    if rc != 0:
        return _result(False, method, "install", t0, log, notes)

    return _result(True, method, None, t0, log, notes)


def _result(success, method, stage_failed, t0, log, notes):
    import time
    return {
        "attempted": True,
        "success": success,
        "method": method,
        "stage_failed": stage_failed,
        "duration_s": round(time.time() - t0, 1),
        "log_tail": "\n".join(log)[-4000:],
        "notes": notes,
    }
