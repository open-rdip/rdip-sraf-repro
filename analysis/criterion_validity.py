"""
Phase-1 journal-extension analysis: criterion-level predictive validity of FAIR-R.

Motivation
----------
The SRAF conference paper reports a null result: the aggregate FAIR-R score does
not predict reproduction outcomes (rho ~ 0.10-0.16, n.s.), while a single
deterministic feature -- the presence of a software licence -- does (OR ~ 7.3).
This script asks *why*, at the level of individual rubric criteria.

Q1  Variance audit.      How much of the 100-point FAIR-R budget actually varies
                         across the corpus? A criterion that is absent (or
                         partial) for every repository contributes nothing to
                         discrimination no matter how many points it carries.
Q2  Predictive validity. Which individual criteria correlate with Level-1
                         outcomes (dependency resolution, build), after
                         multiple-comparison correction?
Q3  Instrument revision. Does an empirically re-weighted "FAIR-R v2", built only
                         from criteria that vary, discriminate better than the
                         standards-derived v1? Weights are derived INSIDE each
                         cross-validation fold, so the comparison is honest.

Statistics hardening (addresses the small-sample fragility of the conference
version): Firth penalized logistic regression with penalized likelihood-ratio
p-values, Benjamini-Hochberg FDR and Bonferroni correction, and cross-validated
AUC reported alongside p-values.

This file is N1 and is deliberately specific to FAIR-R. The instrument-neutral
machinery it used to own now lives in `analysis/audit_core.py` and
`analysis/instruments/`, so that N2 can ask the same question of F-UJI,
howfairis and the ML Reproducibility Checklist. Nothing about the computation
changed in that move: the output of this script is byte-identical to the
version committed before the split, and `tests/test_audit_core.py` pins it.

Usage:  python3 analysis/criterion_validity.py
"""
from __future__ import annotations

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

from analysis.audit_core import (  # noqa: E402
    MIN_MINORITY, bh_fdr, firth_logistic, firth_plr_test, minority_count,
)
from analysis.instruments.sraf import (  # noqa: E402
    ALL_CRITERIA, CATALOGUE, CRIT_DIM, LEVEL_FACTOR, RESULTS_DIR, STUDY_ID_RE,
    build_frame, derive_c_max, load_studies,
)

OUT_MD = REPO_ROOT / "analysis" / "criterion_validity.md"
OUT_CSV = REPO_ROOT / "analysis" / "criterion_table.csv"


# ------------------------------------------------------------------------ main
def main() -> int:
    studies = load_studies()
    c_max = derive_c_max(studies)
    df = build_frame(studies, c_max)
    L: list[str] = []
    A = L.append

    A(f"# Criterion-level predictive validity of FAIR-R (n={len(df)})\n")
    A("Phase-1 analysis for the New Generation Computing extension. "
      "Regenerate with `python3 analysis/criterion_validity.py`.\n")

    # sanity: reconstructed totals should match the stored score
    recon = df[[f"crit::{c}" for c in ALL_CRITERIA]].sum(axis=1)
    err = float(np.max(np.abs(recon - df["fair_r_v1"])))
    A(f"_Reconstruction check: max |sum(criteria) - stored total| = {err:.3f}._\n")

    # ---------------------------------------------------------------- Q1
    A("\n## Q1 — Variance audit: how much of the instrument actually varies?\n")
    A("| dimension | criterion | max pts | levels observed | mean earned | sd | varies |")
    A("|---|---|---:|---|---:|---:|:--:|")
    invariant_budget = 0.0
    total_budget = 0.0
    varying = []
    for c in ALL_CRITERIA:
        col, lvl = df[f"crit::{c}"], df[f"lvl::{c}"]
        counts = lvl.value_counts().to_dict()
        cm = c_max.get(c, 0.0)
        total_budget += cm
        sd = float(col.std())
        varies = sd > 1e-9
        if not varies:
            invariant_budget += cm
        else:
            varying.append(c)
        lv = ", ".join(f"{k}×{v}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
        A(f"| {CRIT_DIM[c]} | {c} | {cm:.2f} | {lv} | {col.mean():.2f} | {sd:.2f} | "
          f"{'yes' if varies else '**no**'} |")
    A("")
    A(f"- Total rubric budget: **{total_budget:.1f}** points across {len(ALL_CRITERIA)} criteria.")
    A(f"- **Invariant on this corpus: {invariant_budget:.1f} points "
      f"({100*invariant_budget/total_budget:.1f}%)** — identical for all {len(df)} repositories, "
      "so they cannot contribute to discrimination.")
    A(f"- Criteria that vary at all: **{len(varying)} of {len(ALL_CRITERIA)}** "
      f"({', '.join(varying)}).")
    live = total_budget - invariant_budget
    A(f"- Live (discriminating) budget: **{live:.1f} points**. This is the ceiling on the "
      "spread of the aggregate score, and explains the tight observed distribution.")

    # ---------------------------------------------------------------- Q2
    A("\n## Q2 — Which criteria predict Level-1 outcomes?\n")
    att = df[df["resolve_success"].notna()].copy()
    A(f"Restricted to the {len(att)} build-attempted repositories "
      f"(resolve n+={int(att['resolve_success'].sum())}, "
      f"build n+={int(att['build_success'].sum())}).\n")
    rows = []
    for outcome in ("resolve_success", "build_success"):
        y = att[outcome].astype(int).to_numpy()
        ps, rhos, names = [], [], []
        for c in varying:
            x = att[f"crit::{c}"].to_numpy(dtype=float)
            if np.std(x) < 1e-9:
                continue
            rho, p = stats.spearmanr(x, y)
            names.append(c); rhos.append(rho); ps.append(p)
        if not ps:
            continue
        fdr = bh_fdr(np.array(ps))
        bonf = np.clip(np.array(ps) * len(ps), 0, 1)
        A(f"\n### Outcome: `{outcome}`\n")
        A("| criterion | rho | raw p | BH-FDR q | Bonferroni p | survives FDR 0.05 |")
        A("|---|---:|---:|---:|---:|:--:|")
        for i, c in enumerate(names):
            A(f"| {c} | {rhos[i]:+.3f} | {ps[i]:.4f} | {fdr[i]:.4f} | {bonf[i]:.4f} | "
              f"{'**yes**' if fdr[i] < 0.05 else 'no'} |")
            rows.append({"outcome": outcome, "criterion": c, "rho": rhos[i],
                         "p_raw": ps[i], "p_fdr": fdr[i], "p_bonferroni": bonf[i]})
        # aggregate for comparison
        rho_a, p_a = stats.spearmanr(att["fair_r_v1"], y)
        A(f"| _aggregate FAIR-R v1_ | {rho_a:+.3f} | {p_a:.4f} | — | — | — |")

    # ---------------------------------------------------------------- Q2b Firth
    A("\n## Q2b — Statistics hardening: Firth penalized logistic regression\n")
    A("The conference model fits 8 predictors on n=86 with ~48 events (~6 events per "
      "variable, below the conventional 10), and reports uncorrected p-values across "
      "8 predictors x 2 outcomes. Firth's penalized likelihood removes the small-sample "
      "bias; p-values are penalized likelihood-ratio tests; correction is over all "
      "predictors within each outcome.\n")
    for outcome in ("resolve_success", "build_success"):
        y = att[outcome].astype(int).to_numpy()
        preds = [c for c in varying
                 if minority_count(att[f"lvl::{c}"]) >= MIN_MINORITY]
        Xc = att[[f"crit::{c}" for c in preds]].to_numpy(dtype=float)
        Xc = (Xc - Xc.mean(0)) / np.where(Xc.std(0) > 0, Xc.std(0), 1)
        X = np.column_stack([np.ones(len(y)), Xc])
        beta, _ = firth_logistic(X, y)
        ps = [firth_plr_test(X, y, j) for j in range(1, X.shape[1])]
        fdr = bh_fdr(np.array(ps))
        A(f"\n### Outcome: `{outcome}`  (events {int(y.sum())}/{len(y)}, "
          f"{len(preds)} predictors, EPV={y.sum()/max(len(preds),1):.1f})\n")
        A("| predictor (standardised) | Firth coef | odds ratio | penalized LR p | BH-FDR q |")
        A("|---|---:|---:|---:|---:|")
        for i, c in enumerate(preds):
            A(f"| {c} | {beta[i+1]:+.3f} | {np.exp(np.clip(beta[i+1], -30, 30)):.2f} | {ps[i]:.4f} | {fdr[i]:.4f} |")

    # ---------------------------------------------------------------- Q3
    A("\n## Q3 — FAIR-R v2: does dropping the dead weight help?\n")
    A("v2 keeps only criteria that vary and re-weights them by their in-fold "
      "association with the outcome, rescaled to 100 points. Weights are derived "
      "**inside each training fold**, so the comparison is not circular. "
      "10-fold stratified CV, 20 repeats.\n")
    A("| outcome | model | CV AUC (mean ± sd) |")
    A("|---|---|---:|")
    rng = np.random.default_rng(0)
    for outcome in ("resolve_success", "build_success"):
        y = att[outcome].astype(int).to_numpy()
        preds = [c for c in varying
                 if minority_count(att[f"lvl::{c}"]) >= MIN_MINORITY]
        Xall = att[[f"crit::{c}" for c in preds]].to_numpy(dtype=float)
        v1 = att["fair_r_v1"].to_numpy(dtype=float).reshape(-1, 1)
        lic = att["crit::Software licence"].to_numpy(dtype=float).reshape(-1, 1)
        scores = defaultdict(list)
        for rep in range(20):
            skf = StratifiedKFold(n_splits=10, shuffle=True, random_state=rep)
            for tr, te in skf.split(Xall, y):
                # v1 aggregate alone
                m = LogisticRegression(max_iter=1000).fit(v1[tr], y[tr])
                scores["FAIR-R v1 (aggregate)"].append(
                    roc_auc_score(y[te], m.predict_proba(v1[te])[:, 1]))
                # licence-only baseline
                m = LogisticRegression(max_iter=1000).fit(lic[tr], y[tr])
                scores["Software licence only"].append(
                    roc_auc_score(y[te], m.predict_proba(lic[te])[:, 1]))
                # v2: in-fold weights from |point-biserial r| on training rows
                w = []
                for j in range(Xall.shape[1]):
                    xj = Xall[tr, j]
                    w.append(0.0 if np.std(xj) < 1e-9
                             else abs(np.corrcoef(xj, y[tr])[0, 1]))
                w = np.nan_to_num(np.array(w))
                w = w / w.sum() * 100 if w.sum() > 0 else np.ones_like(w)
                v2_tr = (Xall[tr] * w).sum(1).reshape(-1, 1)
                v2_te = (Xall[te] * w).sum(1).reshape(-1, 1)
                m = LogisticRegression(max_iter=1000).fit(v2_tr, y[tr])
                scores["FAIR-R v2 (re-weighted, in-fold)"].append(
                    roc_auc_score(y[te], m.predict_proba(v2_te)[:, 1]))
        for k, v in scores.items():
            A(f"| `{outcome}` | {k} | {np.mean(v):.3f} ± {np.std(v):.3f} |")

    # ---------------------------------------------------------------- synthesis
    A("\n## Reading these results\n")
    A(f"1. **The instrument is mostly constant on this corpus.** {invariant_budget:.1f} of "
      f"{total_budget:.0f} points ({100*invariant_budget/total_budget:.0f}%) are identical "
      f"for all {len(df)} repositories; only {len(varying)} criteria vary at all, and only "
      "three vary enough to enter a model. The aggregate score therefore cannot spread far "
      "(observed sd ~5.2), which is a property of the rubric meeting ML code repositories, "
      "not of the repositories being uniformly good.")
    A("")
    A("2. **The null result is explained, not merely replicated.** Aggregate FAIR-R fails to "
      "predict reproduction because most of its budget is dead weight here. The dimension-level "
      "signal previously seen in *Reusable* is entirely the software-licence criterion: the "
      "other two Reusable criteria are invariant, and the criterion's rho equals the "
      "dimension's exactly.")
    A("")
    A("3. **The licence effect is now robust — with a caveat to report honestly.** In the "
      "multivariable Firth model (3 usable criteria, EPV 15-16, well above the conventional "
      "10) software licence survives BH-FDR correction for both outcomes (q=0.017 resolve, "
      "q=0.028 build). At the bivariate level it does not (q=0.14 across six criteria). The "
      "multivariable model has more power because it adjusts for R2 and R3; both numbers "
      "should appear in the paper rather than only the favourable one.")
    A("")
    A("4. **Re-weighting does not rescue the instrument.** FAIR-R v2 reaches CV AUC ~0.60 "
      "versus ~0.58 for v1 — and a single bit, 'does the repository have a licence', reaches "
      "~0.59 on its own. The differences are well inside one standard deviation. The honest "
      "claim is not 'our v2 is better' but 'no weighting of these criteria yields a useful "
      "predictor; the measurable signal reduces to one deterministic feature'.")
    A("")
    A("5. **Implication for the extension.** This reframes the contribution from *we built a "
      "score* to *we show why FAIR-style scores do not transfer to executable research "
      "artifacts, and identify the small set of deterministic features that do carry signal*. "
      "That is a claim about the FAIR-assessment literature, not only about SRAF.")

    OUT_MD.write_text("\n".join(L) + "\n")
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    print("\n".join(L))
    print(f"\n[criterion_validity] wrote {OUT_MD} and {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
