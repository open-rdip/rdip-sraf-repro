"""Run the Tier-B checks across the corpus, streaming.

Same discipline as the build harness: clone to node-local scratch, check,
persist a small JSON, delete the clone. Nothing accumulates on the 200 GB home
volume. Resumable — a study whose output already exists is skipped, so a
re-submission costs nothing.

Designed to be driven either as a Slurm array (one study per task) or as a
single sequential pass:

    python3 build_harness/run_tier_b_corpus.py --index $SLURM_ARRAY_TASK_ID
    python3 build_harness/run_tier_b_corpus.py --all
    python3 build_harness/run_tier_b_corpus.py --only study012 --online

`--online` additionally HEADs each declared asset URL to test for link rot. It
is off by default so the corpus sweep stays deterministic; run it as a separate
pass and record the date, because link liveness is a property of *when* you
looked, not of the artifact alone.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build_harness"))
from tier_b_checks import RULES_VERSION, run_tier_b  # noqa: E402

REPO_LIST = ROOT / "validation" / "repo_list.csv"
OUT_DIR = Path(os.getenv("TIER_B_OUT", ROOT / "validation" / "tier_b"))
SCRATCH = Path(os.getenv("SLURM_TMPDIR",
                         f"/tmp/{os.getenv('SLURM_JOB_ID', 'local')}"))


def load_corpus() -> list[dict]:
    with open(REPO_LIST) as fh:
        return [r for r in csv.DictReader(fh) if (r.get("study_id") or "").strip()]


def clone(repo_url: str, dest: Path, timeout: int = 300) -> tuple[bool, str]:
    """Shallow clone; no history is needed for a static documentation check."""
    cmd = ["git", "clone", "--depth", "1", "--quiet",
           "--config", "core.askpass=true", repo_url, str(dest)]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true"}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, env=env)
        return (p.returncode == 0,
                (p.stderr or "").strip()[:300] or "ok")
    except subprocess.TimeoutExpired:
        return False, f"clone timed out after {timeout}s"
    except Exception as e:                                        # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def process(row: dict, online: bool, keep: bool = False) -> dict:
    sid = row["study_id"]
    out_path = OUT_DIR / f"{sid}.json"
    if out_path.exists():
        try:
            prev = json.load(open(out_path))
        except Exception:
            prev = {}
        stamp = prev.get("rules_version")
        if stamp == RULES_VERSION:
            print(f"  [skip] {sid} — already done (rules v{stamp})")
            return prev
        # Stale grading: the checks have changed since this file was written.
        # Re-run rather than leaving a corpus that mixes rule versions.
        print(f"  [stale] {sid} — rules v{stamp} != v{RULES_VERSION}, re-running")

    SCRATCH.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f"{sid}_", dir=SCRATCH))
    dest = work / "repo"
    t0 = time.time()
    ok, msg = clone(row["repo_url"], dest)
    try:
        if not ok:
            rec = {"study_id": sid, "repo_url": row["repo_url"],
                   "status": "clone_failed", "error": msg, "checks": {}}
        else:
            rec = run_tier_b(dest, paper_title=row.get("paper_title") or None,
                             online=online)
            rec.update(study_id=sid, repo_url=row["repo_url"], status="ok")
            rec.pop("repo_dir", None)          # scratch path is not reproducible
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)

    rec["duration_s"] = round(time.time() - t0, 1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(rec, open(out_path, "w"), indent=2)

    if rec["status"] == "ok":
        lv = {k: v["level_name"] for k, v in rec["checks"].items()}
        print(f"  [ok]   {sid} {rec['tier_b_level_sum']}/{rec['tier_b_max']} {lv}")
    else:
        print(f"  [fail] {sid} — {rec['error']}")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--index", type=int, help="1-based row, for a Slurm array")
    g.add_argument("--only", help="a single study_id")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--online", action="store_true",
                    help="also HEAD declared asset URLs (link-rot pass)")
    ap.add_argument("--keep", action="store_true", help="do not delete the clone")
    ap.add_argument("--limit", type=int, default=None, help="with --all, stop after N")
    a = ap.parse_args()

    corpus = load_corpus()
    if a.index is not None:
        if not 1 <= a.index <= len(corpus):
            print(f"index {a.index} out of range 1..{len(corpus)}")
            return 1
        rows = [corpus[a.index - 1]]
    elif a.only:
        rows = [r for r in corpus if r["study_id"] == a.only]
        if not rows:
            print(f"no such study: {a.only}")
            return 1
    else:
        rows = corpus[: a.limit] if a.limit else corpus

    print(f"Tier-B sweep: {len(rows)} studies, online={a.online}, out={OUT_DIR}")
    for r in rows:
        process(r, online=a.online, keep=a.keep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
