"""Sweep the corpus extracting deterministic repo-side experimental facts.

This is the repo half of the paper-vs-repo semantic diff (contribution N4).
`repo_facts.extract_repo_facts` finds datasets, hyperparameters, computed
metrics and seeds in a repository's configs and code; this runs it over all 96
studies and persists one small JSON per study.

Same discipline as the Tier-B sweep, and the clone machinery is imported from it
rather than copied: shallow clone to node-local scratch, extract, persist, delete.
Nothing accumulates. Resumable and version-stamped — a study whose output was
written by the current FACTS_VERSION is skipped, and one written by an older
version is re-run, so the corpus never mixes extractor versions.

    python3 build_harness/run_repo_facts_corpus.py --all
    python3 build_harness/run_repo_facts_corpus.py --only study012 --keep
    python3 build_harness/run_repo_facts_corpus.py --index $SLURM_ARRAY_TASK_ID

Note on cost: this clones every repository again. If you are also re-running the
Tier-B sweep, run that first and pass --keep so the clones are still on scratch,
or accept the second clone — it is a few minutes for the whole corpus and keeps
the two sweeps independently resumable.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build_harness"))

from repo_facts import FACTS_VERSION, extract_repo_facts   # noqa: E402
from run_tier_b_corpus import clone, load_corpus           # noqa: E402

OUT_DIR = Path(os.getenv("REPO_FACTS_OUT", ROOT / "validation" / "repo_facts"))
SCRATCH = Path(os.getenv("SLURM_TMPDIR",
                         f"/tmp/{os.getenv('SLURM_JOB_ID', 'local')}"))


def process(row: dict, keep: bool = False) -> dict:
    sid = row["study_id"]
    out_path = OUT_DIR / f"{sid}.json"

    if out_path.exists():
        try:
            prev = json.load(open(out_path))
        except Exception:                                         # noqa: BLE001
            prev = {}
        stamp = prev.get("facts_version")
        if stamp == FACTS_VERSION:
            print(f"  [skip] {sid} — already done (facts v{stamp})")
            return prev
        print(f"  [stale] {sid} — facts v{stamp} != v{FACTS_VERSION}, re-running")

    SCRATCH.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f"{sid}_facts_", dir=SCRATCH))
    dest = work / "repo"
    t0 = time.time()
    ok, msg = clone(row["repo_url"], dest)
    try:
        if not ok:
            rec = {"study_id": sid, "repo_url": row["repo_url"],
                   "facts_version": FACTS_VERSION,
                   "status": "clone_failed", "error": msg,
                   "datasets": [], "hyperparameters": [], "metrics": [], "seeds": []}
        else:
            rec = extract_repo_facts(dest)
            rec.update(study_id=sid, repo_url=row["repo_url"], status="ok")
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)

    rec["duration_s"] = round(time.time() - t0, 1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(rec, open(out_path, "w"), indent=2)

    if rec["status"] == "ok":
        print(f"  [ok]   {sid} "
              f"datasets={len(rec['datasets'])} "
              f"hp={len(rec['hyperparameters'])} "
              f"metrics={len(rec['metrics'])} "
              f"seeds={len(rec['seeds'])}")
    else:
        print(f"  [fail] {sid} — {rec['error']}")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--index", type=int, help="1-based row, for a Slurm array")
    g.add_argument("--only", help="a single study_id")
    g.add_argument("--all", action="store_true")
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

    print(f"Repo-facts sweep: {len(rows)} studies, "
          f"facts v{FACTS_VERSION}, out={OUT_DIR}")
    for r in rows:
        process(r, keep=a.keep)

    done = sorted(OUT_DIR.glob("*.json"))
    ok = sum(1 for p in done
             if (json.load(open(p)) or {}).get("status") == "ok")
    print(f"\nCorpus now has {len(done)} records, {ok} with a usable clone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
