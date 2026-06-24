#!/usr/bin/env python3
"""
Compare obtained vs claimed results and classify reproduction (RQ #20).

Reads result_repro/manifest.yaml (with `obtained` filled in from the runs) and,
for each repo, matches each obtained number to a claimed number (metric +
split), computes the relative error, and classifies:

  reproduced : |obtained-claimed| within tolerance (default 5% rel or 0.01 abs)
  mismatch   : a matched pair outside tolerance
  unmatched  : a claimed number with no obtained counterpart

Repo-level status: reproduced (all claims reproduced) / partial (some) /
mismatch (ran but none match) / run_failed (no obtained) / skipped.

    python -m result_repro.compare_results [--manifest ...] [--tol 0.05]
                                           [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os

import yaml

from evaluation.eval_extraction import names_match, _s

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _num(x):
    """Parse a reported value to float (handles %, commas); None if not numeric."""
    s = _s(x).replace(",", "")
    pct = s.endswith("%")
    s = s[:-1] if pct else s
    try:
        v = float(s)
        return v / 100.0 if pct else v
    except ValueError:
        return None


def classify_pair(claimed, obtained, rel_tol=0.05, abs_tol=0.01) -> str:
    """'reproduced' or 'mismatch' for a matched (claimed, obtained) value pair."""
    c, o = _num(claimed), _num(obtained)
    if c is None or o is None:
        return "reproduced" if _s(claimed) == _s(obtained) else "mismatch"
    if abs(c - o) <= abs_tol:
        return "reproduced"
    denom = abs(c) if abs(c) > 1e-9 else 1.0
    return "reproduced" if abs(c - o) / denom <= rel_tol else "mismatch"


def _metric_match(a, b) -> bool:
    """Metric-name equality, tolerant of short acronyms (acc↔accuracy) but not
    ambiguous 2-char ones (ap vs map)."""
    if names_match(a, b):
        return True
    na, nb = _s(a).replace(" ", ""), _s(b).replace(" ", "")
    if not na or not nb:
        return False
    short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(short) >= 3 and short in long


def _match(claim, obtained_list):
    """Find an obtained item with matching metric + split (lenient)."""
    for o in obtained_list:
        if _metric_match(claim.get("metric"), o.get("metric")) and \
                (not claim.get("split") or not o.get("split")
                 or _s(claim["split"]) == _s(o["split"])):
            return o
    return None


def compare_entry(entry, rel_tol=0.05, abs_tol=0.01) -> dict:
    claimed = entry.get("claimed") or []
    obtained = entry.get("obtained") or []
    status_in = entry.get("status", "pending")
    if status_in == "skipped":
        return {"study_id": entry["study_id"], "status": "skipped", "pairs": []}
    if not obtained:
        return {"study_id": entry["study_id"], "status": "run_failed", "pairs": []}

    pairs, n_repro = [], 0
    for c in claimed:
        o = _match(c, obtained)
        if o is None:
            pairs.append({"metric": c.get("metric"), "claimed": c.get("claimed"),
                          "obtained": None, "result": "unmatched"})
            continue
        res = classify_pair(c.get("claimed"), o.get("value"), rel_tol, abs_tol)
        n_repro += res == "reproduced"
        pairs.append({"metric": c.get("metric"), "claimed": c.get("claimed"),
                      "obtained": o.get("value"), "result": res})

    if claimed and n_repro == len(claimed):
        status = "reproduced"
    elif n_repro > 0:
        status = "partial"
    else:
        status = "mismatch"
    return {"study_id": entry["study_id"], "status": status,
            "n_claimed": len(claimed), "n_reproduced": n_repro, "pairs": pairs}


def summarize(entries, rel_tol=0.05, abs_tol=0.01) -> dict:
    rows = [compare_entry(e, rel_tol, abs_tol) for e in entries]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    ran = [r for r in rows if r["status"] in ("reproduced", "partial", "mismatch")]
    return {"n_repos": len(rows), "status_counts": counts,
            "n_ran": len(ran),
            "reproduced_rate_of_ran": round(
                sum(r["status"] == "reproduced" for r in ran) / len(ran), 3)
                if ran else None,
            "rows": rows}


def print_report(rep):
    print(f"\n=== Result reproducibility ({rep['n_repos']} full-tier repos) ===")
    for k, v in rep["status_counts"].items():
        print(f"  {k:12s}: {v}")
    if rep["reproduced_rate_of_ran"] is not None:
        print(f"  reproduced / ran: {rep['reproduced_rate_of_ran']:.1%} "
              f"({rep['n_ran']} ran)")
    print()
    for r in rep["rows"]:
        if r["status"] in ("skipped", "run_failed", "pending"):
            print(f"  {r['study_id']:9s} {r['status']}")
            continue
        print(f"  {r['study_id']:9s} {r['status']}  "
              f"({r['n_reproduced']}/{r['n_claimed']})")
        for p in r["pairs"]:
            print(f"      {p['metric']:18s} claimed={p['claimed']} "
                  f"obtained={p['obtained']} → {p['result']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=os.path.join(ROOT, "result_repro", "manifest.yaml"))
    ap.add_argument("--tol", type=float, default=0.05, help="relative tolerance")
    ap.add_argument("--abs-tol", type=float, default=0.01)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    entries = yaml.safe_load(open(args.manifest)) or []
    rep = summarize(entries, args.tol, args.abs_tol)
    print_report(rep)
    if args.json:
        json.dump(rep, open(args.json, "w"), indent=2)
        print(f"\n[compare] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
