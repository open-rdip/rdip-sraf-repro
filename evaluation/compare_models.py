#!/usr/bin/env python3
"""
RQ3 side-by-side: score every model's extraction against the ground truth and
print one comparison table (per-field F1 + overall + macro), for a tier.

Model slugs are auto-discovered from data/extractions/<study>__<slug>.json
(or pass --models). This is the table that answers "which open LLM best extracts
reproducibility metadata, and on which fields."

    python evaluation/compare_models.py --tier gold [--strict]
                                        [--models slugA,slugB] [--json out.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import os

from evaluation.eval_extraction import run, FIELDS


def discover_slugs(extractions_dir: str) -> list[str]:
    slugs = set()
    for p in glob.glob(os.path.join(extractions_dir, "*__*.json")):
        base = os.path.splitext(os.path.basename(p))[0]
        if "__" in base:
            slugs.add(base.split("__", 1)[1])
    return sorted(slugs)


def compare(models, extractions_dir, gt_dir, tier="gold", strict=False) -> dict:
    reports = {m: run(m, extractions_dir, gt_dir, tier, strict) for m in models}
    return {"tier": tier, "strict": strict, "models": models, "reports": reports}


def print_table(cmp: dict) -> None:
    models = cmp["models"]
    reports = cmp["reports"]
    mode = "strict" if cmp["strict"] else "lenient"
    short = [m.split("-")[0][:10] if m else m for m in models]   # compact headers
    print(f"\n=== RQ3 model comparison — tier={cmp['tier']} ({mode}) — "
          f"F1 per field ===")
    print(f"  {'field':20s} " + " ".join(f"{s:>10}" for s in short))
    for f in FIELDS:
        row = [reports[m]["per_field_micro"][f]["f1"] for m in models]
        print(f"  {f:20s} " + " ".join(f"{v:10.3f}" for v in row))
    print(f"  {'OVERALL micro F1':20s} "
          + " ".join(f"{reports[m]['overall_micro']['f1']:10.3f}" for m in models))
    print(f"  {'macro F1':20s} "
          + " ".join(f"{reports[m]['macro_f1']:10.3f}" for m in models))
    n = {reports[m]["n_studies"] for m in models}
    print(f"  (studies scored: {sorted(n)})")


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default="gold", choices=["gold", "silver"])
    ap.add_argument("--extractions", default=os.path.join(root, "data", "extractions"))
    ap.add_argument("--ground-truth", default=os.path.join(root, "data", "ground_truth"))
    ap.add_argument("--models", default=None, help="comma-separated slugs (default: auto)")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    models = (args.models.split(",") if args.models
              else discover_slugs(args.extractions))
    if not models:
        print(f"No extraction files found in {args.extractions}")
        return 1
    cmp = compare(models, args.extractions, args.ground_truth, args.tier, args.strict)
    print_table(cmp)
    if args.json:
        json.dump(cmp, open(args.json, "w"), indent=2)
        print(f"\n[compare] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
