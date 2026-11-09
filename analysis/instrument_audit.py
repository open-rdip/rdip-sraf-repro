#!/usr/bin/env python3
"""N2: run the N1 variance audit across several FAIR-style instruments.

The question
------------
N1 found that 57.8 of FAIR-R's 100 points are identical for all 96 repositories,
so the aggregate score cannot discriminate. The obvious objection is that this
says something about SRAF rather than about FAIR assessment. N2 answers it by
putting the same corpus and the same Level-1 outcomes through other
instruments and asking whether they saturate too.

Reading the output
------------------
The headline statistic is the proportion of *criteria* with zero observed
variance. That is the only figure comparable across instruments, because only
FAIR-R has a point budget. The point-weighted figure is printed for weighted
instruments and suppressed for the rest, rather than invented.

Two kinds of invariance must not be conflated, and the report separates them:

  ceiling      every repository satisfies the criterion (FAIR-R's pattern)
  floor        no repository satisfies it
  structural   invariant because of how the corpus was sampled, not because of
               what was measured, e.g. howfairis' "public repository" check on
               a corpus selected for having public repositories

A floor-saturated criterion is not evidence that the literature saturates. It
is usually evidence that the instrument is out of scope for the object type.

    python3 analysis/instrument_audit.py                      # all available
    python3 analysis/instrument_audit.py --instruments sraf   # one
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis import outcomes as oc  # noqa: E402
from analysis.audit_core import (  # noqa: E402
    MIN_MINORITY, bh_fdr, firth_logistic, firth_plr_test, minority_count,
    variance_audit,
)
from analysis.instruments import REGISTRY, load  # noqa: E402
from analysis.instruments.howfairis_fs import STRUCTURAL  # noqa: E402

OUT_MD = REPO_ROOT / "analysis" / "instrument_comparison.md"
OUT_CSV = REPO_ROOT / "analysis" / "instrument_comparison.csv"


def kind_of(frame, crit: str, col: pd.Series) -> str:
    """Why a criterion is invariant: ceiling, floor, or sampling artifact."""
    if crit in STRUCTURAL and frame.name == "howfairis":
        return "structural"
    cm = frame.max_points.get(crit)
    top = cm if cm else 1.0
    v = float(col.iloc[0])
    if abs(v - top) < 1e-9:
        return "ceiling"
    if abs(v) < 1e-9:
        return "floor"
    return "mid"


def audit_one(name: str, A) -> dict | None:
    try:
        frame = load(name)
    except Exception as e:  # noqa: BLE001
        A(f"\n## {name}\n")
        A(f"_Skipped: {type(e).__name__}: {e}_\n")
        return None

    va = variance_audit(frame)
    att = oc.attempted(frame.scores)

    A(f"\n## Instrument: `{name}`  (n={frame.n} scored, {len(att)} build-attempted)\n")
    A("| dimension | criterion | max | levels observed | mean | sd | varies | if invariant |")
    A("|---|---|---:|---|---:|---:|:--:|---|")
    for r in va["rows"]:
        c = r["criterion"]
        lv = ", ".join(f"{k}x{v}" for k, v in sorted(r["levels"].items(),
                                                     key=lambda x: -x[1]))
        mx = f"{r['max_points']:.2f}" if va["weighted"] else "-"
        why = "" if r["varies"] else kind_of(frame, c, frame.scores[f"crit::{c}"])
        A(f"| {r['dimension']} | {c} | {mx} | {lv} | {r['mean']:.2f} | {r['sd']:.2f} | "
          f"{'yes' if r['varies'] else '**no**'} | {why} |")
    A("")
    A(f"- Criteria that vary at all: **{va['n_varying']} of {va['n_criteria']}** "
      f"({100*(1-va['frac_invariant_criteria']):.1f}% of criteria).")
    A(f"- Criteria with a minority class of at least {MIN_MINORITY}, so usable in a "
      f"model: **{len(va['usable'])}** ({', '.join(va['usable']) or 'none'}).")
    if va["weighted"]:
        A(f"- Point budget invariant: **{va['invariant_points']:.1f} of "
          f"{va['total_points']:.0f} ({100*va['frac_invariant_points']:.1f}%)**.")
    else:
        A("- Unweighted instrument, so there is no point budget to report. "
          "Compare the criterion proportion above.")

    # ---- bivariate, corrected
    A("\n### Bivariate association with Level-1 outcomes\n")
    for outcome in oc.OUTCOMES:
        y = att[outcome].astype(int).to_numpy()
        if len(np.unique(y)) < 2:
            A(f"\n`{outcome}`: no variance in this subset "
              f"({int(y.sum())}/{len(y)} succeeded), so no association is "
              "estimable. Widen the instrument's coverage before reading "
              "anything into it.\n")
            continue
        names, rhos, ps = [], [], []
        for c in va["varying"]:
            x = att[f"crit::{c}"].to_numpy(dtype=float)
            if np.std(x) < 1e-9:
                continue
            rho, p = stats.spearmanr(x, y)
            names.append(c); rhos.append(rho); ps.append(p)
        if not ps:
            A(f"\n`{outcome}`: no varying criterion survives into this subset.\n")
            continue
        fdr = bh_fdr(np.array(ps))
        A(f"\n`{outcome}` (events {int(y.sum())}/{len(y)})\n")
        A("| criterion | rho | raw p | BH-FDR q | survives 0.05 |")
        A("|---|---:|---:|---:|:--:|")
        for i, c in enumerate(names):
            A(f"| {c} | {rhos[i]:+.3f} | {ps[i]:.4f} | {fdr[i]:.4f} | "
              f"{'**yes**' if fdr[i] < 0.05 else 'no'} |")
        if frame.aggregate:
            rho_a, p_a = stats.spearmanr(att[frame.aggregate], y)
            A(f"| _aggregate ({frame.aggregate})_ | {rho_a:+.3f} | {p_a:.4f} | - | - |")

    # ---- Firth multivariable
    preds = [c for c in va["varying"]
             if minority_count(att[f"lvl::{c}"]) >= MIN_MINORITY]
    if preds:
        A("\n### Firth penalized logistic regression\n")
        for outcome in oc.OUTCOMES:
            y = att[outcome].astype(int).to_numpy()
            if len(np.unique(y)) < 2:
                A(f"\n`{outcome}`: outcome has no variance in this subset; "
                  "not estimable.\n")
                continue
            Xc = att[[f"crit::{c}" for c in preds]].to_numpy(dtype=float)
            Xc = (Xc - Xc.mean(0)) / np.where(Xc.std(0) > 0, Xc.std(0), 1)
            X = np.column_stack([np.ones(len(y)), Xc])
            beta, _ = firth_logistic(X, y)
            ps = [firth_plr_test(X, y, j) for j in range(1, X.shape[1])]
            fdr = bh_fdr(np.array(ps))
            A(f"\n`{outcome}` (events {int(y.sum())}/{len(y)}, {len(preds)} predictors, "
              f"EPV={y.sum()/max(len(preds),1):.1f})\n")
            A("| predictor (standardised) | coef | odds ratio | penalized LR p | BH-FDR q |")
            A("|---|---:|---:|---:|---:|")
            for i, c in enumerate(preds):
                A(f"| {c} | {beta[i+1]:+.3f} | "
                  f"{np.exp(np.clip(beta[i+1], -30, 30)):.2f} | {ps[i]:.4f} | {fdr[i]:.4f} |")
    else:
        A("\n### Firth penalized logistic regression\n")
        A(f"_No criterion has a minority class of at least {MIN_MINORITY}; "
          "nothing is estimable._\n")

    # ---- cross-validated discrimination
    A("\n### Cross-validated discrimination (10-fold, 20 repeats)\n")
    A("| outcome | model | CV AUC (mean +/- sd) |")
    A("|---|---|---:|")
    cv_rows = []
    for outcome in oc.OUTCOMES:
        y = att[outcome].astype(int).to_numpy()
        if len(np.unique(y)) < 2 or not preds:
            A(f"| `{outcome}` | not estimable | - |")
            continue
        Xall = att[[f"crit::{c}" for c in preds]].to_numpy(dtype=float)
        scores = defaultdict(list)
        for rep in range(20):
            skf = StratifiedKFold(n_splits=10, shuffle=True, random_state=rep)
            for tr, te in skf.split(Xall, y):
                if frame.aggregate:
                    agg = att[frame.aggregate].to_numpy(dtype=float).reshape(-1, 1)
                    m = LogisticRegression(max_iter=1000).fit(agg[tr], y[tr])
                    scores["aggregate score"].append(
                        roc_auc_score(y[te], m.predict_proba(agg[te])[:, 1]))
                if frame.baseline and f"crit::{frame.baseline}" in att:
                    bl = att[f"crit::{frame.baseline}"].to_numpy(dtype=float).reshape(-1, 1)
                    if np.std(bl[tr]) > 0:
                        m = LogisticRegression(max_iter=1000).fit(bl[tr], y[tr])
                        scores[f"{frame.baseline} only"].append(
                            roc_auc_score(y[te], m.predict_proba(bl[te])[:, 1]))
                w = []
                for j in range(Xall.shape[1]):
                    xj = Xall[tr, j]
                    w.append(0.0 if np.std(xj) < 1e-9
                             else abs(np.corrcoef(xj, y[tr])[0, 1]))
                w = np.nan_to_num(np.array(w))
                w = w / w.sum() * 100 if w.sum() > 0 else np.ones_like(w)
                m = LogisticRegression(max_iter=1000).fit(
                    (Xall[tr] * w).sum(1).reshape(-1, 1), y[tr])
                scores["re-weighted, in-fold"].append(roc_auc_score(
                    y[te], m.predict_proba((Xall[te] * w).sum(1).reshape(-1, 1))[:, 1]))
        for k, v in scores.items():
            A(f"| `{outcome}` | {k} | {np.mean(v):.3f} +/- {np.std(v):.3f} |")
            cv_rows.append({"instrument": name, "outcome": outcome, "model": k,
                            "auc_mean": np.mean(v), "auc_sd": np.std(v)})

    va["_cv"] = cv_rows
    va["_n_attempted"] = len(att)
    return va


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instruments", default=None,
                    help=f"comma-separated; default all of {sorted(REGISTRY)}")
    args = ap.parse_args()
    names = ([s.strip() for s in args.instruments.split(",") if s.strip()]
             if args.instruments else list(REGISTRY))

    L: list[str] = []
    A = L.append
    A("# N2 - Does FAIR-style saturation generalise beyond SRAF?\n")
    A("Same corpus, same Level-1 outcomes, different instruments. "
      "Regenerate with `python3 analysis/instrument_audit.py`.\n")

    audits = [a for a in (audit_one(n, A) for n in names) if a]

    if audits:
        A("\n## Cross-instrument summary\n")
        A("| instrument | n | criteria | varying | usable | invariant criteria | "
          "invariant points |")
        A("|---|---:|---:|---:|---:|---:|---:|")
        for a in audits:
            pts = (f"{100*a['frac_invariant_points']:.1f}%"
                   if a["weighted"] else "n/a (unweighted)")
            A(f"| {a['instrument']} | {a['n']} | {a['n_criteria']} | {a['n_varying']} | "
              f"{len(a['usable'])} | {100*a['frac_invariant_criteria']:.1f}% | {pts} |")
        A("")
        A("Read the last two columns together. The criterion proportion is the "
          "comparable figure; the point proportion exists only where the instrument "
          "defines a budget.")
        A("")
        A("Before concluding that an instrument saturates, check the *if invariant* "
          "column in its own table above. Ceiling invariance across several "
          "instruments supports the N1 claim. Floor invariance usually means the "
          "instrument was never designed for executable research artifacts, which "
          "is a finding about scope rather than about the literature, and "
          "structural invariance is an artifact of how this corpus was sampled.")

        rows = [r for a in audits for r in a.get("_cv", [])]
        if rows:
            pd.DataFrame(rows).to_csv(OUT_CSV, index=False)

    OUT_MD.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[instrument_audit] wrote {OUT_MD}"
          + (f" and {OUT_CSV}" if OUT_CSV.exists() else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
