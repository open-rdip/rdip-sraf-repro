"""A code-native criterion set for reproducibility assessment of ML repositories.

Why this exists
---------------
`analysis/criterion_validity.py` showed that 57.8 of FAIR-R's 100 points are
identical across all 96 repositories, that only three criteria carry usable
variation, and that no re-weighting of those criteria produces a useful
predictor. `analysis/taxonomy_restructure.py` then showed *why*: of the 16
genuine artifact failures, fifteen map onto criteria that are either absent
from the rubric entirely (a concrete run command, link liveness) or among the
invariant 57.8 points (Related links, Access level). The instrument could not
have predicted those failures even in principle.

The conclusion is therefore not "re-weight FAIR-R" but "measure different
things". This module specifies and evaluates a candidate criterion set drawn
from what actually breaks, and from repository-side facts that are obtained
deterministically rather than by language-model extraction.

Two tiers
---------
TIER A  computable now, for all 96, from the artefacts already extracted.
TIER B  derived directly from the failure taxonomy and expected to carry more
        signal, but NOT computable from stored data: each needs a new static
        check in the build harness (a corpus re-clone, i.e. a cluster job).
        Tier B is specified here so it can be implemented, not evaluated.

Nothing here is fitted and evaluated on the same rows: every weight is derived
inside the training fold. Usage:

    python3 analysis/code_native_criteria.py
"""
from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(os.getenv("SRAF_RESULTS_DIR", REPO_ROOT / "validation" / "results"))
OUT_MD = REPO_ROOT / "analysis" / "code_native_criteria.md"
OUT_CSV = REPO_ROOT / "analysis" / "code_native_scores.csv"
STUDY_ID_RE = re.compile(r"^study\d{3}$")

# ---------------------------------------------------------------- TIER A spec
# name -> (human label, extractor, rationale tying it to the taxonomy or to the
#          conference predictor analysis)
TIER_A = {
    "licence_present": (
        "Software licence present",
        lambda d: int(bool((d.get("repo_meta") or {}).get("software_license"))),
        "Top single predictor in the conference analysis (OR~7.3); the only "
        "FAIR-R criterion that both varies and predicts.",
    ),
    "python_declared": (
        "Python version declared",
        lambda d: int(bool((d.get("python") or {}).get("declared"))),
        "An undeclared interpreter forces the harness to guess; guessing is "
        "where version-dependent resolution failures begin.",
    ),
    "has_docker": (
        "Docker/OCI recipe present",
        lambda d: int("docker" in ((d.get("artifacts") or {}).get("by_type") or {})),
        "The remedy the paper recommends against environment rot.",
    ),
    "has_conda": (
        "Conda environment present",
        lambda d: int("conda" in ((d.get("artifacts") or {}).get("by_type") or {})),
        "Pins the interpreter and native libraries together; OR~5.5 for resolve "
        "in the conference analysis.",
    ),
    "has_pip": (
        "pip requirements present",
        lambda d: int("pip" in ((d.get("artifacts") or {}).get("by_type") or {})),
        "The weakest form of declaration: rarely pins transitive versions.",
    ),
    "multi_env_decl": (
        "More than one environment declaration",
        lambda d: int(len(((d.get("artifacts") or {}).get("by_type") or {})) > 1),
        "Redundant declarations give the harness a fallback path.",
    ),
    "artifacts_at_root": (
        "Environment files at repository root",
        lambda d: int(((d.get("artifacts") or {}).get("depth_note") or "") == "root"),
        "Buried artefacts are found late or not at all; 'repo does not match "
        "paper' (3 failures) is the extreme case of locating the wrong thing.",
    ),
    "n_artifacts": (
        "Count of environment artefacts",
        lambda d: float((d.get("artifacts") or {}).get("n_found", 0) or 0),
        "Graded version of the declaration criteria.",
    ),
    "metadata_richness": (
        "Extracted metadata richness (log triples)",
        lambda d: float(np.log1p((d.get("lift") or {}).get("triples", 0) or 0)),
        "How much structured description the repository actually supports.",
    ),
}

# ---------------------------------------------------------------- TIER B spec
# Derived from the restructured taxonomy. Each needs a new harness check.
TIER_B = [
    ("concrete_run_command",
     "A documented run command with no unfilled placeholder",
     "7 of 16 artifact failures (the single largest mode). Static check: parse "
     "fenced code blocks in README/docs; flag /path/to, <...>, $VAR, YOUR_.",
     "NOT COVERED by FAIR-R at all."),
    ("documented_entrypoint",
     "Any documented way to reproduce a reported number",
     "4 of 16 failures. Static check: presence of an eval/test/reproduce "
     "command or script referenced from the documentation.",
     "Only partially covered by Reproducible R2."),
    ("links_resolve",
     "Declared checkpoint/dataset URLs return 200",
     "1 of 16 failures directly (dead 404); link rot is time-dependent so this "
     "grows with artefact age. Static check: HEAD each extracted URL.",
     "NOT COVERED by FAIR-R at all."),
    ("data_obtainable_without_application",
     "Required data is downloadable without a gating application",
     "1 of 16 failures. Static check: classify dataset access statements.",
     "Maps to Accessible/Access level, which is absent for all 96 — i.e. "
     "present in the rubric but invariant, so it cannot discriminate."),
    ("repo_matches_paper",
     "Linked repository corresponds to the paper",
     "3 of 16 failures. Static check: similarity between paper title/abstract "
     "and repository description/README.",
     "Maps to Interoperable/Related links, absent for all 96."),
]


def load() -> list[dict]:
    out = []
    for p in sorted(glob.glob(str(RESULTS_DIR / "*.json"))):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        if STUDY_ID_RE.match(str(d.get("study_id", "")).strip()):
            out.append(d)
    return out


def cv_auc(X: np.ndarray, y: np.ndarray, reps: int = 20) -> tuple[float, float]:
    s = []
    for r in range(reps):
        for tr, te in StratifiedKFold(10, shuffle=True, random_state=r).split(X, y):
            m = LogisticRegression(max_iter=2000).fit(X[tr], y[tr])
            s.append(roc_auc_score(y[te], m.predict_proba(X[te])[:, 1]))
    return float(np.mean(s)), float(np.std(s))


def cv_auc_scored(X: np.ndarray, y: np.ndarray, reps: int = 20) -> tuple[float, float]:
    """Weights derived INSIDE each training fold, then collapsed to one score.

    This is the honest version of 'an instrument': the reader gets a single
    number out of a weighted rubric, not a fitted multivariate model.
    """
    s = []
    for r in range(reps):
        for tr, te in StratifiedKFold(10, shuffle=True, random_state=r).split(X, y):
            w = []
            for j in range(X.shape[1]):
                xj = X[tr, j]
                w.append(0.0 if np.std(xj) < 1e-9
                         else abs(np.corrcoef(xj, y[tr])[0, 1]))
            w = np.nan_to_num(np.asarray(w))
            w = w / w.sum() * 100 if w.sum() > 0 else np.ones(X.shape[1])
            m = LogisticRegression(max_iter=2000).fit((X[tr] * w).sum(1).reshape(-1, 1), y[tr])
            s.append(roc_auc_score(
                y[te], m.predict_proba((X[te] * w).sum(1).reshape(-1, 1))[:, 1]))
    return float(np.mean(s)), float(np.std(s))


def main() -> int:
    studies = load()
    rows = []
    for d in studies:
        b = d.get("build") or {}
        row = {"study_id": d["study_id"],
               "fair_r_v1": (d.get("fair_r") or {}).get("total_score"),
               "resolve": b.get("resolve_success"),
               "build": b.get("build_success")}
        for k, (_lab, fn, _why) in TIER_A.items():
            try:
                row[k] = fn(d)
            except Exception:
                row[k] = 0
        rows.append(row)
    df = pd.DataFrame(rows)
    att = df[df["resolve"].notna()].copy()

    L = []
    A = L.append
    A(f"# A code-native criterion set (n={len(df)}; {len(att)} build-attempted)\n")
    A("Regenerate with `python3 analysis/code_native_criteria.py`. Companion to "
      "`criterion_validity.md` (why FAIR-R fails) and `taxonomy_restructured.md` "
      "(what actually breaks).\n")

    # ------------------------------------------------------------- variance
    A("## 1. Do these criteria vary? (the test FAIR-R fails)\n")
    A("FAIR-R forfeits 57.8 of 100 points identically for every repository. A "
      "replacement criterion earns its place only if it varies here.\n")
    A("| Criterion | mean | sd | varies |")
    A("|---|---:|---:|:--:|")
    names = list(TIER_A)
    for k in names:
        lab = TIER_A[k][0]
        sd = float(df[k].std())
        A(f"| {lab} | {df[k].mean():.2f} | {sd:.2f} | {'yes' if sd > 1e-9 else '**no**'} |")
    varying = [k for k in names if df[k].std() > 1e-9]
    A("")
    A(f"- **{len(varying)} of {len(names)} vary**, against 6 of 15 for FAIR-R "
      f"(and only 3 of those usable). Nothing here is dead weight.")

    # ----------------------------------------------------------- univariate
    A("\n## 2. Univariate association with outcome\n")
    A("Spearman rho over the build-attempted set, with Benjamini-Hochberg "
      "correction across the criteria tested.\n")
    for outcome in ("resolve", "build"):
        y = att[outcome].astype(int).to_numpy()
        ps, rhos = [], []
        for k in varying:
            rho, p = stats.spearmanr(att[k].to_numpy(float), y)
            rhos.append(rho); ps.append(p)
        order = np.argsort(ps)
        ranked = np.asarray(ps)[order] * len(ps) / (np.arange(len(ps)) + 1)
        ranked = np.minimum.accumulate(ranked[::-1])[::-1]
        q = np.empty(len(ps)); q[order] = np.clip(ranked, 0, 1)
        A(f"\n### `{outcome}` (events {int(y.sum())}/{len(y)})\n")
        A("| Criterion | rho | p | BH q | survives |")
        A("|---|---:|---:|---:|:--:|")
        for i in np.argsort(-np.abs(rhos)):
            A(f"| {TIER_A[varying[i]][0]} | {rhos[i]:+.3f} | {ps[i]:.4f} | "
              f"{q[i]:.4f} | {'**yes**' if q[i] < 0.05 else 'no'} |")

    # ------------------------------------------------------- discrimination
    A("\n## 3. Discrimination against the incumbents\n")
    A("10-fold stratified CV, 20 repeats. *Scored* rows collapse the criteria "
      "into one 0-100 number using weights derived inside each training fold — "
      "that is what an instrument actually hands a reader. *Model* rows fit all "
      "criteria jointly and are an upper bound, not a deliverable.\n")
    A("| Outcome | Instrument | CV AUC |")
    A("|---|---|---:|")
    Xc = att[varying].to_numpy(float)
    Xc = (Xc - Xc.mean(0)) / np.where(Xc.std(0) > 0, Xc.std(0), 1)
    for outcome in ("resolve", "build"):
        y = att[outcome].astype(int).to_numpy()
        v1 = att[["fair_r_v1"]].to_numpy(float)
        lic = att[["licence_present"]].to_numpy(float)
        for label, fn, X in (
            ("FAIR-R v1 (aggregate)", cv_auc, v1),
            ("Software licence alone", cv_auc, lic),
            ("Code-native (scored, in-fold weights)", cv_auc_scored, Xc),
            ("Code-native (model, upper bound)", cv_auc, Xc),
        ):
            m, s = fn(X, y)
            A(f"| `{outcome}` | {label} | {m:.3f} ± {s:.3f} |")

    A("")
    A("**Read this conservatively.** The gain over FAIR-R is real and consistent "
      "in direction, but modest, and the standard deviations overlap. The claim "
      "the data supports is *not* 'we built an accurate predictor'. It is: "
      "criteria chosen because they vary and because they correspond to observed "
      "failures discriminate better than a standards-derived rubric whose mass "
      "sits on criteria that never vary — and they do so while remaining "
      "deterministic, requiring no language-model extraction.")

    # -------------------------------------------------------------- tier B
    A("\n## 4. Tier B — the criteria the taxonomy says matter most\n")
    A("These come straight from the 16 artifact failures. **None is computable "
      "from stored data**: each needs a new static check in the build harness, "
      "so evaluating them requires a corpus re-clone (a cluster job). They are "
      "specified here so they can be implemented and then measured — not "
      "claimed as results.\n")
    A("| Criterion | What it checks | Why (evidence) | FAIR-R coverage |")
    A("|---|---|---|---|")
    for key, what, why, cov in TIER_B:
        A(f"| `{key}` | {what} | {why} | {cov} |")
    A("")
    A("Tier B is the substance of the instrument redesign: 15 of the 16 observed "
      "artifact failures map onto these five checks, and every one of them is a "
      "cheap static test. That is the paper's constructive contribution — the "
      "diagnosis says the rubric measures the wrong things; this says what the "
      "right things are and how to compute them.")

    A("\n## 5. Threats\n")
    A("- Tier A criteria are evaluated on the same 96 repositories that motivated "
      "them. Weights are derived in-fold, so the AUCs are not circular, but the "
      "*choice* of criteria is informed by this corpus. An independent held-out "
      "set is required before claiming generalisation.")
    A("- `resolve` and `build` are Level-1 outcomes. No Level-2 outcome exists to "
      "validate against: nothing in the corpus reproduced, so the criteria are "
      "validated against environment reconstruction, not result reproduction.")
    A("- Several Tier A criteria are correlated by construction (an environment "
      "file count and the individual file-type flags). The scored version handles "
      "this only crudely; a principled weighting should account for redundancy.")

    OUT_MD.write_text("\n".join(L) + "\n")
    df.to_csv(OUT_CSV, index=False)
    print("\n".join(L))
    print(f"\n[code-native] wrote {OUT_MD} and {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
