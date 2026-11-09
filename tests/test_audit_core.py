"""Tests for the instrument-agnostic variance audit (N2 refactor).

The important test here is `test_sraf_regression_pin`. The N2 work split
`criterion_validity.py` into a generic core plus adapters, and the whole point
of that split is that it changed no numbers. The pin fails loudly if a future
edit to the shared core moves the N1 result.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.audit_core import (  # noqa: E402
    MIN_MINORITY, bh_fdr, firth_logistic, minority_count, variance_audit,
)
from analysis.instruments.base import InstrumentFrame  # noqa: E402


# --------------------------------------------------------------- fixtures
def make_frame(spec: dict[str, list[str]], max_points: dict | None = None,
               name: str = "t") -> InstrumentFrame:
    """Build a frame from {criterion: [level, level, ...]}."""
    level_val = {"absent": 0.0, "partial": 0.5, "full": 1.0,
                 "fail": 0.0, "pass": 1.0}
    n = len(next(iter(spec.values())))
    data = {"study_id": [f"study{i+1:03d}" for i in range(n)]}
    for c, levels in spec.items():
        mx = (max_points or {}).get(c, 1.0)
        data[f"crit::{c}"] = [mx * level_val[l] for l in levels]
        data[f"lvl::{c}"] = list(levels)
    df = pd.DataFrame(data).set_index("study_id")
    return InstrumentFrame(name=name, criteria=list(spec),
                           dim_of={c: "d" for c in spec}, scores=df,
                           max_points=max_points or {})


# --------------------------------------------------------------- base shape
def test_validate_rejects_missing_columns():
    df = pd.DataFrame({"study_id": ["study001"], "crit::A": [1.0]}).set_index("study_id")
    f = InstrumentFrame(name="t", criteria=["A"], dim_of={"A": "d"}, scores=df)
    with pytest.raises(ValueError, match="missing score columns"):
        f.validate()


def test_validate_rejects_unindexed_scores():
    df = pd.DataFrame({"crit::A": [1.0], "lvl::A": ["pass"]})
    f = InstrumentFrame(name="t", criteria=["A"], dim_of={"A": "d"}, scores=df)
    with pytest.raises(ValueError, match="indexed by study_id"):
        f.validate()


def test_validate_rejects_unknown_baseline():
    f = make_frame({"A": ["pass", "fail"]})
    f.baseline = "Nope"
    with pytest.raises(ValueError, match="not one of the criteria"):
        f.validate()


def test_binary_instrument_is_unweighted():
    """A 5-check binary instrument must not report a point budget."""
    f = make_frame({f"C{i}": ["pass", "fail"] for i in range(5)})
    assert f.weighted is False
    va = variance_audit(f)
    assert va["frac_invariant_points"] is None


def test_graded_instrument_is_weighted():
    f = make_frame({"A": ["full", "absent"], "B": ["full", "full"]},
                   max_points={"A": 7.5, "B": 5.0})
    assert f.weighted is True


# ------------------------------------------------------------ variance audit
def test_variance_audit_separates_varying_from_invariant():
    f = make_frame({
        "varies":    ["full", "absent", "full", "absent"],
        "ceiling":   ["full", "full", "full", "full"],
        "floor":     ["absent", "absent", "absent", "absent"],
    })
    va = variance_audit(f)
    assert va["varying"] == ["varies"]
    assert set(va["invariant"]) == {"ceiling", "floor"}
    assert va["n_varying"] == 1
    assert va["frac_invariant_criteria"] == pytest.approx(2 / 3)


def test_variance_audit_point_budget():
    f = make_frame({"a": ["full", "absent"], "dead": ["absent", "absent"]},
                   max_points={"a": 40.0, "dead": 60.0})
    va = variance_audit(f)
    assert va["total_points"] == pytest.approx(100.0)
    assert va["invariant_points"] == pytest.approx(60.0)
    assert va["frac_invariant_points"] == pytest.approx(0.60)


def test_usable_requires_minority_threshold():
    """A criterion that differs on one repo varies but is not usable."""
    levels = ["full"] * 20 + ["absent"]
    f = make_frame({"rare": levels, "common": ["full"] * 11 + ["absent"] * 10})
    va = variance_audit(f)
    assert "rare" in va["varying"]
    assert "rare" not in va["usable"]
    assert "common" in va["usable"]


def test_minority_count():
    assert minority_count(pd.Series(["a"] * 10)) == 0
    assert minority_count(pd.Series(["a"] * 8 + ["b"] * 2)) == 2
    assert minority_count(pd.Series(["a"] * 5 + ["b"] * 3 + ["c"] * 2)) == 5


# ------------------------------------------------------------------- stats
def test_bh_fdr_known_values():
    q = bh_fdr(np.array([0.01, 0.02, 0.03, 0.04, 0.05]))
    assert q[0] == pytest.approx(0.05)
    assert np.all(np.diff(q) >= -1e-12)      # monotone after ordering
    assert np.all(q <= 1.0)


def test_bh_fdr_is_never_smaller_than_raw_p():
    p = np.array([0.001, 0.2, 0.5, 0.9])
    assert np.all(bh_fdr(p) >= p - 1e-12)


def test_firth_converges_under_separation():
    """Plain MLE diverges on separated data; Firth must stay finite."""
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    x = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=float)
    X = np.column_stack([np.ones(len(y)), x])
    beta, ll = firth_logistic(X, y)
    assert np.all(np.isfinite(beta))
    assert np.isfinite(ll)
    assert beta[1] > 0


# ------------------------------------------------------- outcome joining
def test_attempted_drops_duplicate_outcome_columns():
    """The adapter may ship its own outcome copy; the loader must win."""
    from analysis import outcomes as oc
    scores = pd.DataFrame({
        "study_id": ["study001", "study002"],
        "crit::A": [1.0, 0.0],
        "lvl::A": ["pass", "fail"],
        "resolve_success": [False, False],   # deliberately wrong
        "build_success": [False, False],
    }).set_index("study_id")
    truth = pd.DataFrame({
        "study_id": ["study001", "study002"],
        "resolve_success": [True, True],
        "build_success": [True, False],
    }).set_index("study_id")
    # patch the loader rather than touching the real corpus
    orig = oc.load
    try:
        oc.load = lambda: truth
        att = oc.attempted(scores)
    finally:
        oc.load = orig
    assert list(att["resolve_success"]) == [True, True]
    assert "resolve_success_x" not in att.columns


# ------------------------------------------------------------ regression pin
@pytest.mark.skipif(
    not (REPO_ROOT / "validation" / "results").exists(),
    reason="corpus results not present")
def test_sraf_regression_pin():
    """The refactor must not move the N1 numbers.

    57.8 of 100 points invariant, 6 of 15 criteria varying, 3 usable. These
    are the figures quoted in the journal extension plan and the progress
    deck; if this test fails, the paper is wrong somewhere.
    """
    from analysis.instruments import load
    va = variance_audit(load("sraf"))
    assert va["n"] == 96
    assert va["n_criteria"] == 15
    assert va["n_varying"] == 6
    assert len(va["usable"]) == 3
    assert set(va["usable"]) == {
        "Software licence",
        "Methodological transparency (R2)",
        "Data provenance (R3)",
    }
    assert va["total_points"] == pytest.approx(100.0, abs=0.05)
    assert va["invariant_points"] == pytest.approx(57.8, abs=0.05)
