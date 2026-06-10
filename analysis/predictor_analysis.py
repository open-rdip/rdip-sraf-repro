"""Phase IV predictor analysis (RQ1, RQ4).

RQ1 — which metadata categories predict reconstruction failure: logistic
      regression of the resolve / build outcome on metadata predictors, with
      odds ratios and p-values.
RQ4 — does FAIR-R correlate with the outcome: Spearman rho + p.

Predictors come from each result JSON (artifact presence/placement, license,
triple count) joined with repo_list.csv (declared seed, stars, tier).

Run:
  ~/envs/sraf/bin/python -m analysis.predictor_analysis
Needs pandas, scipy, statsmodels (in requirements.txt).
"""
from __future__ import annotations
import glob
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(os.getenv("SRAF_RESULTS_DIR", REPO_ROOT / "validation" / "results"))
REPO_LIST = REPO_ROOT / "validation" / "repo_list.csv"
OUT_DIR = REPO_ROOT / "analysis"

# Candidate predictors (intersected with those that actually vary in the data).
PREDICTORS = [
    "has_docker", "has_conda", "has_pip", "in_subdir",
    "license_present", "has_seed", "log_stars", "log_triples",
]


def load_frame() -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(str(RESULTS_DIR / "*.json"))):
        r = json.load(open(f))
        a = r.get("artifacts", {}) or {}
        by = a.get("by_type", {}) or {}
        b = r.get("build", {}) or {}
        fr = r.get("fair_r", {}) or {}
        meta = r.get("repo_meta", {}) or {}
        lift = r.get("lift", {}) or {}
        attempted = b.get("attempted", False)
        rows.append({
            "study_id": r.get("study_id"),
            "has_docker": int("docker" in by),
            "has_conda": int("conda" in by),
            "has_pip": int("pip" in by),
            "in_subdir": int(a.get("depth_note") in ("subdir", "deep")),
            "license_present": int(bool(meta.get("software_license"))),
            "triples": lift.get("triples", 0) or 0,
            "resolve_success": (int(b["resolve_success"])
                                if b.get("resolve_success") is not None else np.nan),
            "build_success": int(bool(b.get("build_success"))) if attempted else np.nan,
            "fair_r": fr.get("total_score", np.nan),
        })
    df = pd.DataFrame(rows)

    if REPO_LIST.exists():
        rl = pd.read_csv(REPO_LIST)
        cols = [c for c in ("study_id", "has_seed", "stars", "final_tier") if c in rl.columns]
        rl = rl[cols].copy()
        if "has_seed" in rl:
            rl["has_seed"] = rl["has_seed"].astype(str).str.lower().isin(["true", "1"]).astype(int)
        df = df.merge(rl, on="study_id", how="left")

    df["log_stars"] = np.log1p(df["stars"].fillna(0)) if "stars" in df else 0.0
    df["log_triples"] = np.log1p(df["triples"].fillna(0))
    if "has_seed" not in df:
        df["has_seed"] = 0
    return df


def _usable_predictors(df: pd.DataFrame) -> list[str]:
    """Keep predictors present and with variance (constant cols break Logit)."""
    out = []
    for p in PREDICTORS:
        if p in df.columns and df[p].nunique(dropna=True) > 1:
            out.append(p)
    return out


def logit_report(df: pd.DataFrame, outcome: str) -> list[str]:
    import statsmodels.api as sm
    lines = [f"### Logistic regression — outcome: {outcome}\n"]
    d = df.dropna(subset=[outcome]).copy()
    d[outcome] = d[outcome].astype(int)
    n, pos = len(d), int(d[outcome].sum())
    lines.append(f"- n={n}, positive={pos} ({pos}/{n})")
    if d[outcome].nunique() < 2:
        lines.append(f"- no variance in {outcome} — regression not estimable.\n")
        return lines
    preds = _usable_predictors(d)
    if not preds:
        lines.append("- no predictors with variance.\n")
        return lines

    X = sm.add_constant(d[preds].astype(float))
    y = d[outcome]
    try:
        res = sm.Logit(y, X).fit(disp=0, maxiter=200)
        params, pvals, conv = res.params, res.pvalues, True
    except Exception as e:  # perfect separation / non-convergence
        res = sm.Logit(y, X).fit_regularized(disp=0, alpha=1.0)
        params, pvals, conv = res.params, pd.Series(np.nan, index=res.params.index), False
        lines.append(f"- NOTE: MLE did not converge ({type(e).__name__}); "
                     f"L2-regularised estimate, p-values unavailable.")
    lines.append("")
    lines.append("| predictor | coef | odds ratio | p-value |")
    lines.append("|---|---:|---:|---:|")
    for name in params.index:
        if name == "const":
            continue
        p = pvals.get(name, np.nan)
        star = " *" if (conv and p < 0.05) else ""
        pstr = "—" if np.isnan(p) else f"{p:.3f}"
        lines.append(f"| {name} | {params[name]:+.2f} | {np.exp(params[name]):.2f} | {pstr}{star} |")
    lines.append("")
    return lines


def spearman_report(df: pd.DataFrame) -> list[str]:
    from scipy.stats import spearmanr
    lines = ["### Spearman correlation — FAIR-R vs outcome (RQ4)\n"]
    if df["fair_r"].nunique(dropna=True) < 2:
        lines.append(f"- FAIR-R is constant in this run "
                     f"(value={df['fair_r'].dropna().iloc[0] if df['fair_r'].notna().any() else 'NA'}); "
                     f"correlation undefined until the extracted dimensions add variance.\n")
        return lines
    for outcome in ("resolve_success", "build_success"):
        d = df.dropna(subset=["fair_r", outcome])
        if len(d) > 3 and d[outcome].nunique() > 1:
            rho, p = spearmanr(d["fair_r"], d[outcome])
            lines.append(f"- {outcome}: rho={rho:+.3f}, p={p:.3f}  (n={len(d)})")
    lines.append("")
    return lines


def main():
    df = load_frame()
    if df.empty:
        print(f"No result JSONs in {RESULTS_DIR}")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "predictor_table.csv", index=False)

    lines = [f"# Phase IV predictor analysis — {len(df)} repos\n"]
    lines += logit_report(df, "resolve_success")
    lines += logit_report(df, "build_success")
    lines += spearman_report(df)
    report = "\n".join(lines)
    (OUT_DIR / "predictor_analysis.md").write_text(report)
    print(report)
    print(f"\nWrote {OUT_DIR/'predictor_analysis.md'} and predictor_table.csv")


if __name__ == "__main__":
    main()
