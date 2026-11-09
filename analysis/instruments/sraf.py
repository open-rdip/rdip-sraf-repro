"""SRAF FAIR-R adapter.

The loading logic is lifted verbatim out of `criterion_validity.py` so the N1
report reproduces bit for bit after the refactor. `criterion_validity.py` now
imports these functions rather than defining them.

FAIR-R is the one genuinely weighted instrument in the comparison: 100 points
over 15 criteria in 5 dimensions, graded absent/partial/full. Its results
files record only *gaps*, so a criterion's maximum has to be recovered rather
than read, which is what `derive_c_max` does.
"""
from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.instruments.base import InstrumentFrame

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = Path(os.getenv("SRAF_RESULTS_DIR", REPO_ROOT / "validation" / "results"))

STUDY_ID_RE = re.compile(r"^study\d{3}$")
LEVEL_FACTOR = {"absent": 0.0, "partial": 0.5, "full": 1.0}

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


# ------------------------------------------------------------------- adapter
def frame() -> InstrumentFrame:
    """SRAF FAIR-R as an InstrumentFrame for the cross-instrument audit."""
    studies = load_studies()
    if not studies:
        raise RuntimeError(f"no SRAF result files under {RESULTS_DIR}")
    c_max = derive_c_max(studies)
    df = build_frame(studies, c_max).set_index("study_id")
    f = InstrumentFrame(
        name="sraf",
        criteria=list(ALL_CRITERIA),
        dim_of=dict(CRIT_DIM),
        scores=df,
        max_points=c_max,
        aggregate="fair_r_v1",
        # The conference paper's one robust predictor; kept as the explicit
        # single-feature baseline so v2 is judged against it rather than
        # against chance.
        baseline="Software licence",
    )
    f.validate()
    return f
