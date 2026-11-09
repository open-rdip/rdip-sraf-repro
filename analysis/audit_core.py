"""Instrument-agnostic statistics for the variance audit (N1 and N2).

Lifted verbatim from `criterion_validity.py` so that the SRAF numbers in the
committed report are reproduced bit for bit. Nothing here knows what an
instrument is; it takes a design matrix and an outcome vector.

Binary instruments are fine. Firth's penalised likelihood was adopted for N1
because the corpus is small and several criteria are near-separated; that is
if anything more necessary for a 5-check binary instrument than for a graded
one, since a binary criterion with a small minority class separates easily.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

# A criterion enters a regression only if its minority level is observed at
# least this many times. Criteria that differ on one or two repositories are
# numerically separated (and mutually collinear), which makes penalised
# likelihood diverge; they carry no usable information either way.
MIN_MINORITY = 5


def minority_count(levels: pd.Series) -> int:
    vc = levels.value_counts()
    return 0 if len(vc) < 2 else int(vc.iloc[1:].sum())


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


# ------------------------------------------------------------------ corrections
def bh_fdr(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(ranked, 0, 1)
    return out


# --------------------------------------------------------------- variance audit
def variance_audit(frame) -> dict:
    """Per-criterion spread, and what is invariant across the whole corpus.

    Returns both denominators: criterion counts (comparable across every
    instrument) and point budget (only meaningful for a weighted one).
    """
    df = frame.scores
    rows, varying, invariant = [], [], []
    inv_pts = tot_pts = 0.0
    for c in frame.criteria:
        col, lvl = df[f"crit::{c}"], df[f"lvl::{c}"]
        cm = float(frame.max_points.get(c, 0.0))
        tot_pts += cm
        sd = float(col.std())
        varies = sd > 1e-9
        (varying if varies else invariant).append(c)
        if not varies:
            inv_pts += cm
        rows.append({
            "criterion": c,
            "dimension": frame.dim_of.get(c, frame.name),
            "max_points": cm,
            "levels": lvl.value_counts().to_dict(),
            "mean": float(col.mean()),
            "sd": sd,
            "varies": varies,
            "minority": minority_count(lvl),
            "usable": varies and minority_count(lvl) >= MIN_MINORITY,
        })
    return {
        "instrument": frame.name,
        "n": frame.n,
        "rows": rows,
        "varying": varying,
        "invariant": invariant,
        "n_criteria": len(frame.criteria),
        "n_varying": len(varying),
        "frac_invariant_criteria": (len(invariant) / len(frame.criteria)
                                    if frame.criteria else 0.0),
        "usable": [r["criterion"] for r in rows if r["usable"]],
        "weighted": frame.weighted,
        "total_points": tot_pts,
        "invariant_points": inv_pts,
        "frac_invariant_points": (inv_pts / tot_pts) if tot_pts else None,
    }
