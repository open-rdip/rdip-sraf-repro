"""Aggregate the per-study repo-facts sweep into one corpus record.

The sweep writes `validation/repo_facts/<study>.json`, one file per study, which
is right for a resumable array job but useless for analysis or for citing a
corpus-level number. This merges them and reports the coverage statistics the
paper needs.

    python3 analysis/repo_facts_summary.py
    python3 analysis/repo_facts_summary.py --out-dir analysis

Writes three things:

    repo_facts_corpus.json   every record, one array — the archival artifact
    repo_facts_summary.csv   one row per study, for analysis and the appendix
    (stdout)                 corpus coverage, the numbers to quote

The coverage table is the point. `metric_never_computed` can only be decided for
a study whose repository exposes some metric computation; a corpus where that is
rare bounds what the semantic diff can claim, and that bound has to be reported
rather than discovered by a reviewer.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTS_DIR = Path(os.getenv("REPO_FACTS_OUT", ROOT / "validation" / "repo_facts"))
KINDS = ("datasets", "hyperparameters", "metrics", "seeds")


def load_all() -> list[dict]:
    out = []
    for p in sorted(FACTS_DIR.glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            print(f"  WARNING: {p.name} is not valid JSON — skipped")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(ROOT / "analysis"))
    a = ap.parse_args()
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_all()
    if not records:
        print(f"no records in {FACTS_DIR} — run the sweep first")
        return 1

    versions = Counter(r.get("facts_version") for r in records)
    if len(versions) > 1:
        print("REFUSING TO SUMMARISE: the corpus mixes extractor versions "
              f"{dict(versions)}.")
        print("Re-run the sweep; it re-does stale records automatically.")
        return 2

    ok = [r for r in records if r.get("status") == "ok"]
    failed = [r for r in records if r.get("status") != "ok"]

    # ── per-study rows ───────────────────────────────────────────────────────
    csv_path = out_dir / "repo_facts_summary.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["study_id", "status", "n_files_read",
                    "n_datasets", "n_hyperparameters", "n_metrics", "n_seeds",
                    "metric_signals", "datasets", "metrics"])
        for r in records:
            sigs = sorted({m.get("signal", "") for m in r.get("metrics") or []})
            w.writerow([
                r.get("study_id"), r.get("status"), r.get("n_files_read", 0),
                *[len(r.get(k) or []) for k in KINDS],
                "|".join(s for s in sigs if s),
                "|".join(d.get("canonical", "") for d in r.get("datasets") or []),
                "|".join(m.get("canonical", "") for m in r.get("metrics") or []),
            ])

    json_path = out_dir / "repo_facts_corpus.json"
    json_path.write_text(json.dumps(records, indent=2))

    # ── corpus coverage ──────────────────────────────────────────────────────
    print(f"Repo facts, extractor v{list(versions)[0]}: "
          f"{len(records)} studies, {len(ok)} cloned, {len(failed)} failed\n")

    print("Coverage — studies with at least one fact of each kind:")
    for kind in KINDS:
        n = sum(1 for r in ok if r.get(kind))
        pct = 100 * n / len(ok) if ok else 0
        print(f"  {kind:17s} {n:3d}/{len(ok)}  ({pct:4.1f}%)")

    sig = Counter(m.get("signal") for r in ok for m in r.get("metrics") or [])
    if sig:
        print("\nMetric detections by signal "
              "(report precision per class, not pooled):")
        total = sum(sig.values())
        for s, n in sig.most_common():
            print(f"  {s:13s} {n:4d}  ({100*n/total:4.1f}%)")

    top = Counter(d.get("canonical") for r in ok for d in r.get("datasets") or [])
    if top:
        print("\nMost common datasets:")
        for name, n in top.most_common(8):
            print(f"  {name:18s} {n:3d} studies")

    no_metric = [r["study_id"] for r in ok if not r.get("metrics")]
    if no_metric:
        print(f"\n{len(no_metric)} studies expose no machine-identifiable metric "
              "computation.")
        print("  metric_never_computed is UNDECIDABLE for these — the diff reports")
        print("  repo_silent, not a conflict. Hand-check a sample before writing")
        print("  this up: a detector gap and an artifact-quality finding look")
        print("  identical in this table.")
        print("  " + ", ".join(no_metric[:12]) + ("..." if len(no_metric) > 12 else ""))

    if failed:
        print(f"\nClone failures ({len(failed)}):")
        for r in failed:
            print(f"  {r.get('study_id')}: {str(r.get('error'))[:80]}")

    print(f"\nwrote {csv_path}")
    print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
