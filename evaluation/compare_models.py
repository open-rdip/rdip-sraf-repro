#!/usr/bin/env python3
"""
RQ3 side-by-side: score every model's extraction against the ground truth and
print comparison tables (per-field F1 + headline + overall), for a tier.

Prints both EXACT and FUZZY name-matching by default (a defensible range), with
the paper-derivable HEADLINE separated from the repo-derived fields, and N/A for
fields with no gold support.

Model slugs are auto-discovered from data/extractions/<study>__<slug>.json.

    python -m evaluation.compare_models --tier gold [--strict]
                                        [--match exact|fuzzy|both]
                                        [--models slugA,slugB] [--json out.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.eval_extraction import run, PAPER_FIELDS, REPO_FIELDS


def discover_slugs(extractions_dir: str) -> list[str]:
    slugs = set()
    for p in glob.glob(os.path.join(extractions_dir, "*__*.json")):
        base = os.path.splitext(os.path.basename(p))[0]
        if "__" in base:
            slugs.add(base.split("__", 1)[1])
    return sorted(slugs)


def _short(slug):
    for kw in ("qwen", "llama", "mistral", "mixtral", "gemma", "phi",
               "deepseek", "gpt", "falcon"):
        if kw in (slug or "").lower():
            return kw
    return (slug or "")[:12]


def compare(models, extractions_dir, gt_dir, tier="gold", strict=False,
            fuzzy=False) -> dict:
    reports = {m: run(m, extractions_dir, gt_dir, tier, strict, fuzzy)
               for m in models}
    return {"tier": tier, "strict": strict, "fuzzy": fuzzy,
            "models": models, "reports": reports}


def _cell(m):
    return "  n/a " if m["na"] else f"{m['f1']:6.3f}"


def print_table(cmp: dict) -> None:
    models, reports = cmp["models"], cmp["reports"]
    mode = ("strict" if cmp["strict"] else "lenient") + \
           ("/fuzzy" if cmp["fuzzy"] else "/exact")
    short = [_short(m) for m in models]
    print(f"\n=== RQ3 comparison — tier={cmp['tier']} ({mode}) — F1 ===")
    print(f"  {'field':20s} " + " ".join(f"{s:>9}" for s in short))
    for f in PAPER_FIELDS:
        print(f"  {f:20s} " + " ".join(_cell(reports[m]['per_field'][f])
                                       for m in models))
    print(f"  {'HEADLINE (paper)':20s} "
          + " ".join(f"{reports[m]['headline_micro']['f1']:6.3f}" for m in models))
    print("  " + "-" * 56)
    for f in REPO_FIELDS:
        print(f"  {f+' [repo]':20s} " + " ".join(_cell(reports[m]['per_field'][f])
                                                 for m in models))
    print(f"  {'overall (all)':20s} "
          + " ".join(f"{reports[m]['overall_micro']['f1']:6.3f}" for m in models))
    print(f"  {'macro F1 (paper)':20s} "
          + " ".join(f"{reports[m]['macro_f1']:6.3f}" for m in models))
    n = {reports[m]["n_studies"] for m in models}
    print(f"  (studies scored: {sorted(n)})")


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default="gold", choices=["gold", "silver"])
    ap.add_argument("--match", default="both", choices=["exact", "fuzzy", "both"])
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

    modes = [False, True] if args.match == "both" else [args.match == "fuzzy"]
    out = {"tier": args.tier, "strict": args.strict, "models": models, "tables": []}
    for fuzzy in modes:
        cmp = compare(models, args.extractions, args.ground_truth, args.tier,
                      args.strict, fuzzy)
        print_table(cmp)
        out["tables"].append(cmp)
    print("\nLegend: " + " · ".join(f"{_short(m)}={m}" for m in models))
    if args.json:
        json.dump(out, open(args.json, "w"), indent=2)
        print(f"\n[compare] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
