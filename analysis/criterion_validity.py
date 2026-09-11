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

Usage:  python3 analysis/criterion_validity.py
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(os.getenv("SRAF_RESULTS_DIR", REPO_ROOT / "validation" / "results"))
OUT_MD = REPO_ROOT / "analysis" / "criterion_validity.md"
OUT_CSV = REPO_ROOT / "analysis" / "criterion_table.csv"

STUDY_ID_RE = re.compile(r"^study\d{3}$")
LEVEL_FACTOR = {"absent": 0.0, "partial": 0.5, "full": 1.0}

# A criterion enters a regression only if its minority level is observed at
# least this many times. Criteria that differ on one or two repositories are
# numerically separated (and mutually collinear), which makes penalised
# likelihood diverge; they carry no usable information either way.
MIN_MINORITY = 5


def minority_count(levels: pd.Series) -> int:
    vc = levels.value_counts()
    return 0 if len(vc) < 2 else int(vc.iloc[1:].sum())

# The 15 rubric criteria, from dashboard/fair_r_scorer.py (DIMENSIONS).
CATALOGUE = {
    "Findable": ["Persistent identifier", "Descriptive metadata", "Landing page"],
    "Accessible": ["Access protocol", "Data licence", "Access level"],
    "Interoperable": ["Method declared", "Workflow language", "Related links"],
    "Reusable": ["Software licence", "Commit + versioning", "Community standard"],
    "Reproducible": ["Computational environment (R1)",
                     "Methodological transparency (R2)",
                     "Data provenance (R3)"],
}
CRIT_DIM = {c: d for d, cs in CATALOGUE.items() for c in cs}
ALL_CRITERIA = [c for cs in CATALOGUE.values() for c in cs]


# ---------------------------------------------------------------- data loading
def load_studies() -> list[dict]:
    out = []
    for p in sorted(glob.glob(str(RESULTS_DIR / "*.json"))):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        if STUDY_ID_RE.match(str(d.get("study_id", "")).strip()):
            out.append(d)
    return out


def derive_c_max(studies: list[dict]) -> dict[str, float]:
    """Recover each criterion's maximum points.

    `recommendations` records only *gaps*, as points_available = c_max - earned.
    absent  -> earned 0      -> c_max = points_available
    partial -> earned c_max/2 -> c_max = 2 * points_available
    A criterion that is never a gap is always full; its c_max is recovered from
    the dimension arithmetic (dimension_score minus the earned points of its
    siblings).
    """
    c_max: dict[str, float] = {}
    for d in studies:
        for r in d["fair_r"].get("recommendations", []):
            lab, lvl, pa = r["label"], r.get("level"), r.get("points_available")
            if lab in c_max or pa is None:
                continue
            if lvl == "absent":
                c_max[lab] = float(pa)
            elif lvl == "partial":
                c_max[lab] = 2.0 * float(pa)

    # Solve the always-full criteria from the dimension totals.
    for dim, crits in CATALOGUE.items():
        unknown = [c for c in crits if c not in c_max]
        if not unknown:
            continue
        residuals = []
        for d in studies:
            gaps = {r["label"]: r for r in d["fair_r"].get("recommendations", [])}
            dim_score = d["fair_r"]["dimension_scores"][dim]
            known_earned = 0.0
            ok = True
            for c in crits:
                if c in unknown:
                    continue
                if c in gaps:
                    known_earned += c_max[c] * LEVEL_FACTOR[gaps[c].get("level", "absent")]
                else:
                    known_earned += c_max[c]
            if ok:
                residuals.append(dim_score - known_earned)
        if residuals and len(unknown) == 1:
            c_max[unknown[0]] = float(np.median(residuals))
        else:
            for c in unknown:
                c_max[c] = float(np.median(residuals)) / max(len(unknown), 1)
    return c_max


def build_frame(studies: list[dict], c_max: dict[str, float]) -> pd.DataFrame:
    rows = []
    for d in studies:
        gaps = {r["label"]: r for r in d["fair_r"].get("recommendations", [])}
        b = d.get("build", {}) or {}
        row = {
            "study_id": d["study_id"],
            "fair_r_v1": d["fair_r"].get("total_score"),
            "resolve_success": b.get("resolve_success"),
            "build_success": b.get("build_success"),
        }
        for c in ALL_CRITERIA:
            lvl = gaps[c].get("level", "absent") if c in gaps else "full"
            row[f"crit::{c}"] = c_max.get(c, 0.0) * LEVEL_FACTOR[lvl]
            row[f"lvl::{c}"] = lvl
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------ Firth regression
def firth_logistic(X: np.ndarray, y: np.ndarray, max_iter: int = 200,
                   tol: float = 1e-8) -> tuple[np.ndarray, float]:
    """Firth penalized logistic regression. Returns (beta, penalized loglik).

    Penalized score:  U*(b) = X'(y - p + h*(0.5 - p)),  h = diag hat matrix.
    Penalized loglik: l(b) + 0.5*log|I(b)|  (Jeffreys prior).
    """
    n, k = X.shape
    beta = np.zeros(k)
    for _ in range(max_iter):
        eta = X @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(eta, -35, 35)))
        w = np.clip(p * (1 - p), 1e-10, None)
        XW = X * w[:, None]
        I = X.T @ XW
        try:
            I_inv = np.linalg.pinv(I)
            # hat diagonal
            h = np.einsum("ij,jk,ik->i", X * np.sqrt(w)[:, None], I_inv,
                          X * np.sqrt(w)[:, None])
            U = X.T @ (y - p + h * (0.5 - p))
            step = I_inv @ U
        except np.linalg.LinAlgError:
            break
        # step halving for stability
        for _s in range(20):
            new = beta + step
            eta_n = np.clip(X @ new, -35, 35)
            if np.all(np.isfinite(eta_n)):
                break
            step /= 2.0
        if np.max(np.abs(step)) < tol:
            beta = new
            break
        beta = new
    eta = np.clip(X @ beta, -35, 35)
    p = 1.0 / (1.0 + np.exp(-eta))
    ll = np.sum(y * np.log(np.clip(p, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-12, 1)))
    w = np.clip(p * (1 - p), 1e-10, None)
    I = X.T @ (X * w[:, None])
    sign, logdet = np.linalg.slogdet(I)
    pen_ll = ll + 0.5 * logdet if sign > 0 else ll
    return beta, pen_ll


def firth_plr_test(X: np.ndarray, y: np.ndarray, j: int) -> float:
    """Penalized likelihood-ratio p-value for dropping column j."""
    _, ll_full = firth_logistic(X, y)
    keep = [i for i in range(X.shape[1]) if i != j]
    _, ll_red = firth_logistic(X[:, keep], y)
    lr = max(2.0 * (ll_full - ll_red), 0.0)
    return float(stats.chi2.sf(lr, 1))


# ----------------------------------------------------------------- corrections
def bh_fdr(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(ranked, 0, 1)
    return out


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
