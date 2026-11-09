"""howfairis / fair-software.eu adapter (N2, second instrument).

Five binary recommendations, no point budget, no graded levels. The level
labels are pass/fail rather than absent/partial/full, which is why the audit
core keys off `lvl::` strings instead of assuming the FAIR-R grading.

One structural caveat to state in the paper rather than discover in review:
the `repository` check asks whether the software is in a public version
control repository, and every study in this corpus was sampled *because* it
has a public GitHub repository. So that criterion is invariant by
construction, not by measurement. It is kept in the table and flagged, since
removing it would quietly flatter the instrument.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from analysis.instruments.base import InstrumentFrame

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = Path(os.getenv("SRAF_HOWFAIRIS_DIR", REPO_ROOT / "data" / "howfairis"))

CHECKS = ["repository", "license", "registry", "citation", "checklist"]

# Human-readable labels, so the cross-instrument table reads consistently.
LABEL = {
    "repository": "Public repository",
    "license": "Software licence",
    "registry": "Package registry",
    "citation": "Citation metadata",
    "checklist": "Quality checklist",
}

# Invariant by sampling design, not by measurement. See module docstring.
STRUCTURAL = {"Public repository"}


def load_records() -> list[dict]:
    out = []
    for p in sorted(CACHE_DIR.glob("study*.json")):
        try:
            d = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("error") or any(d.get(k) is None for k in CHECKS):
            continue
        out.append(d)
    return out


def frame() -> InstrumentFrame:
    recs = load_records()
    if not recs:
        raise RuntimeError(
            f"no usable howfairis records under {CACHE_DIR}. Run:\n"
            "  ~/.venvs/howfairis/bin/python scripts/collect_howfairis.py")
    rows = []
    for d in recs:
        row = {"study_id": d["study_id"], "howfairis_total": int(d["n_passed"])}
        for k in CHECKS:
            lab = LABEL[k]
            passed = bool(d[k])
            row[f"crit::{lab}"] = 1.0 if passed else 0.0
            row[f"lvl::{lab}"] = "pass" if passed else "fail"
        rows.append(row)
    df = pd.DataFrame(rows).set_index("study_id")
    f = InstrumentFrame(
        name="howfairis",
        criteria=[LABEL[k] for k in CHECKS],
        dim_of={LABEL[k]: "fair-software.eu" for k in CHECKS},
        scores=df,
        max_points={},            # unweighted: every check counts the same
        aggregate="howfairis_total",
        baseline="Software licence",
    )
    f.validate()
    return f
