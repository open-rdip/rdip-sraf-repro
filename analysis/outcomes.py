"""Level-1 reproduction outcomes, keyed by study_id.

Outcomes belong to the corpus, not to any instrument: the same resolve and
build results are the dependent variable for FAIR-R, howfairis, F-UJI and the
checklist alike. Keeping them in one place is what makes the N2 comparison a
comparison of instruments rather than of pipelines.
"""
from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(os.getenv("SRAF_RESULTS_DIR", REPO_ROOT / "validation" / "results"))
STUDY_ID_RE = re.compile(r"^study\d{3}$")

OUTCOMES = ("resolve_success", "build_success")


def load() -> pd.DataFrame:
    rows = []
    for p in sorted(glob.glob(str(RESULTS_DIR / "*.json"))):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        sid = str(d.get("study_id", "")).strip()
        if not STUDY_ID_RE.match(sid):
            continue
        b = d.get("build", {}) or {}
        rows.append({"study_id": sid,
                     "resolve_success": b.get("resolve_success"),
                     "build_success": b.get("build_success")})
    if not rows:
        raise RuntimeError(f"no outcome records under {RESULTS_DIR}")
    return pd.DataFrame(rows).set_index("study_id")


def attempted(frame_scores: pd.DataFrame) -> pd.DataFrame:
    """Join outcomes onto an instrument's scores, keeping build-attempted rows.

    An inner join is deliberate. If an instrument covers fewer studies than the
    corpus (F-UJI will, since it is scoped to the DOI subset), the analysis
    must run on the intersection and the report must say what n it used.
    """
    out = load()
    # An adapter may carry its own copy of the outcome columns (the SRAF frame
    # does, for backwards compatibility with N1). This loader is authoritative,
    # so drop the duplicates rather than suffixing them and silently analysing
    # the wrong column later.
    scores = frame_scores.drop(columns=[c for c in OUTCOMES
                                        if c in frame_scores.columns])
    joined = scores.join(out, how="inner")
    return joined[joined["resolve_success"].notna()].copy()
