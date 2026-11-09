"""N5 — cross-level linkage: does anything predict how deep a study gets?

## The outcome had to be re-specified, and that is itself a finding

The plan asked whether Level-0 (metadata) and Level-1 (build) features predict
Level-2 (result reproduction). They cannot, and not because n is small:

    result_repro/results/summary.json
      n_total 26 · n_recipe_extracted 13 · n_ran 0 · n_reproduced 0

**The Level-2 outcome has no variance.** Nothing reproduced, so "reproduced" is
constant and no model of it is estimable. Reporting a null here would be a
category error — there is no null to report, only an unanswerable question.

What the funnel does contain is *depth*. Two stages have variance and are
analysed instead:

    in_scope           17 of 26   attemptable at all, vs skipped as out-of-scale,
                                  hardware-bound, or repo/paper mismatched
    recipe_extracted   13 of 26   an execution recipe was obtained

Both are strictly deeper than anything N1 modelled (N1 covered resolve_success
and build_success), so this is new rather than a re-run.

## Why this is the analysis that makes N4 more than descriptive

The predictors include the repo-side facts and paper↔repo conflict counts built
for N4. Until now those were descriptive statistics. Testing them against funnel
depth asks whether they carry information about outcome — the same move N1 made
for the FAIR-R criteria, and the only thing that turns a detector into a signal.

## Statistical discipline

n = 26 with 13 events. That is roughly one event per two predictors even
univariately, so:

- **Univariate only.** A multivariable model on 26 rows would be indefensible.
- **Firth penalized logistic regression** with penalized likelihood-ratio tests,
  reusing `criterion_validity.py` so N1 and N5 are estimated identically.
- Benjamini-Hochberg across predictors within each outcome.
- Report the **effect direction and interval**, not significance alone.

**This is hypothesis-generating.** The output says so on every run, because a
reader who sees only the table will otherwise read it as a result.

    python3 analysis/cross_level.py
    python3 analysis/cross_level.py --model <slug> --json out.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis"))

from criterion_validity import firth_logistic, firth_plr_test  # noqa: E402

DEFAULT_MODEL = "qwen-qwen2-5-14b-instruct-gptq-int8"
SKIP_PREFIX = "SKIP"


def load_funnel() -> pd.DataFrame:
    d = json.loads((ROOT / "result_repro" / "results" / "summary.json").read_text())
    rows = []
    for r in d["rows"]:
        reason = str(r.get("reason") or "")
        rows.append({
            "study_id": r["study_id"],
            # Skipped studies were excluded by design (out-of-scale, hardware-bound,
            # repo/paper mismatch) — not failures of the artifact.
            "in_scope": int(not reason.startswith(SKIP_PREFIX)),
            "recipe_extracted": int(
                bool(r.get("recipe_command")) and str(r.get("recipe_command")) != "None"),
        })
    return pd.DataFrame(rows)


def load_level01() -> pd.DataFrame:
    rows = list(csv.DictReader(open(ROOT / "analysis" / "results_summary.csv")))
    out = []
    for r in rows:
        def num(k):
            try:
                return float(r[k])
            except (TypeError, ValueError):
                return np.nan
        out.append({"study_id": r["study_id"],
                    "fair_r": num("fair_r"),
                    "n_artifacts": num("n_artifacts"),
                    "triples": num("triples"),
                    "has_docker": 1.0 if r.get("has_docker") == "True" else 0.0,
                    "has_commit": 1.0 if r.get("has_commit") == "True" else 0.0})
    return pd.DataFrame(out)


def load_repo_facts() -> pd.DataFrame:
    rows = []
    for p in sorted((ROOT / "validation" / "repo_facts").glob("*.json")):
        d = json.loads(p.read_text())
        if d.get("status") != "ok":
            continue
        rows.append({"study_id": d["study_id"],
                     "n_datasets": len(d.get("datasets") or []),
                     "n_hyperparameters": len(d.get("hyperparameters") or []),
                     "n_metrics": len(d.get("metrics") or []),
                     "n_seeds": len(d.get("seeds") or [])})
    return pd.DataFrame(rows)


def load_tier_b() -> pd.DataFrame:
    rows = []
    for p in sorted((ROOT / "validation" / "tier_b").glob("*.json")):
        d = json.loads(p.read_text())
        if d.get("status") != "ok":
            continue
        rows.append({"study_id": d["study_id"],
                     "tier_b_level_sum": d.get("tier_b_level_sum", np.nan)})
    return pd.DataFrame(rows)


def load_conflicts(model_slug: str) -> pd.DataFrame:
    p = ROOT / "validation" / f"diff_{model_slug}.json"
    if not p.exists():
        return pd.DataFrame(columns=["study_id", "n_conflicts", "n_decidable"])
    rows = []
    for r in json.loads(p.read_text()):
        if r.get("status") != "ok":
            continue
        rows.append({"study_id": r["study_id"],
                     "n_conflicts": r["counts"]["conflicts"],
                     "n_decidable": r["counts"]["decidable_types"]})
    return pd.DataFrame(rows)


PREDICTORS = ["fair_r", "tier_b_level_sum", "n_artifacts", "triples",
              "has_docker", "has_commit",
              "n_datasets", "n_hyperparameters", "n_metrics", "n_seeds",
              "n_conflicts", "n_decidable"]
OUTCOMES = ["in_scope", "recipe_extracted"]


def bh(pvals: list[float]) -> list[float]:
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    adj = np.empty(n)
    prev = 1.0
    for rank, i in enumerate(order[::-1]):
        k = n - rank
        prev = min(prev, p[i] * n / k)
        adj[i] = prev
    return list(adj)


def analyse(df: pd.DataFrame, outcome: str) -> list[dict]:
    y = df[outcome].to_numpy(dtype=float)
    rows = []
    for name in PREDICTORS:
        if name not in df.columns:
            continue
        x = df[name].to_numpy(dtype=float)
        ok = ~np.isnan(x) & ~np.isnan(y)
        xi, yi = x[ok], y[ok]
        if len(xi) < 8 or len(set(yi)) < 2 or np.nanstd(xi) == 0:
            rows.append({"predictor": name, "n": int(ok.sum()),
                         "skipped": "no variance or too few rows"})
            continue
        # Standardise so odds ratios are per standard deviation and comparable.
        xs = (xi - xi.mean()) / (xi.std() or 1.0)
        X = np.column_stack([np.ones(len(xs)), xs])
        beta, _ = firth_logistic(X, yi)
        p = firth_plr_test(X, yi, 1)
        rows.append({"predictor": name, "n": int(ok.sum()),
                     "events": int(yi.sum()),
                     "beta": float(beta[1]), "odds_ratio": float(np.exp(beta[1])),
                     "p_raw": float(p)})
    live = [r for r in rows if "p_raw" in r]
    for r, q in zip(live, bh([r["p_raw"] for r in live])):
        r["p_fdr"] = float(q)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--json")
    a = ap.parse_args()

    df = load_funnel()
    for other in (load_level01(), load_repo_facts(), load_tier_b(),
                  load_conflicts(a.model)):
        if len(other):
            df = df.merge(other, on="study_id", how="left")

    print("N5 — cross-level linkage")
    print(f"model slug for conflict features: {a.model}")
    print(f"\nfunnel rows: {len(df)}")
    for o in OUTCOMES:
        print(f"  {o:18s} {int(df[o].sum())} of {len(df)}")
    print("\n  n_ran = 0, n_reproduced = 0 — the Level-2 reproduction outcome has")
    print("  NO VARIANCE and is not modelled. Depth is modelled instead.")

    results = {}
    for o in OUTCOMES:
        rows = analyse(df, o)
        results[o] = rows
        print(f"\n── {o} ──")
        print(f"  {'predictor':20s} {'n':>4s} {'OR/SD':>8s} {'p':>8s} {'p_fdr':>8s}")
        for r in sorted(rows, key=lambda r: r.get("p_raw", 9)):
            if "p_raw" not in r:
                print(f"  {r['predictor']:20s} {r['n']:4d}   — {r['skipped']}")
                continue
            print(f"  {r['predictor']:20s} {r['n']:4d} {r['odds_ratio']:8.2f} "
                  f"{r['p_raw']:8.3f} {r['p_fdr']:8.3f}")

    print("\n" + "=" * 72)
    print("EXPLORATORY. n = 26 with 13 events is roughly one event per two")
    print("predictors even univariately. No multivariable model is fitted, and")
    print("none should be. Read the direction of effect, not the p-values;")
    print("quote the counts alongside any odds ratio. This generates hypotheses")
    print("for a larger corpus — it does not test them.")
    print("=" * 72)

    if a.json:
        Path(a.json).write_text(json.dumps(
            {"model_slug": a.model, "n": len(df),
             "outcome_counts": {o: int(df[o].sum()) for o in OUTCOMES},
             "level2_note": "n_ran=0, n_reproduced=0; outcome has no variance",
             "results": results}, indent=2))
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
