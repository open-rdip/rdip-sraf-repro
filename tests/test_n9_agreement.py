"""Tests for the N9 agreement coefficients.

These run without any annotation data, which is the point: the statistics are
pinned before the second annotator exists, so a disagreement with the numbers
later cannot be settled by adjusting the estimator.
"""
from __future__ import annotations

import numpy as np
import pytest

from analysis.n9_agreement import (MIN_FIELD_N, bootstrap_ci, cohen_kappa,
                                   gwet_ac1, per_field, Row)


def _vec(spec):
    return np.array([1 if c == "K" else 0 for c in spec])


def test_perfect_agreement_is_one():
    a = _vec("KKDDKDDD")
    assert cohen_kappa(a, a) == pytest.approx(1.0)
    assert gwet_ac1(a, a) == pytest.approx(1.0)


def test_hand_computed_two_by_two():
    """n=100, both annotators mark 30 keep, 20 of those shared."""
    a = np.array([1] * 30 + [0] * 70)
    b = np.array([1] * 20 + [0] * 10 + [1] * 10 + [0] * 60)
    po, pe = 0.80, 0.3 * 0.3 + 0.7 * 0.7
    assert cohen_kappa(a, b) == pytest.approx((po - pe) / (1 - pe))
    peg = 2 * 0.3 * 0.7
    assert gwet_ac1(a, b) == pytest.approx((po - peg) / (1 - peg))


def test_degenerate_marginal_is_handled_not_divided_by_zero():
    """The two coefficients diverge here, and the divergence is deliberate.

    With one label used throughout, Cohen's pe is 1 and kappa is undefined;
    Gwet's pe is 0 and AC1 is 1.0. AC1 is arithmetically right and the
    agreement is real, but no discrimination has been shown, so per_field
    flags the field rather than suppressing the number.
    """
    ones = np.ones(50, dtype=int)
    assert np.isnan(cohen_kappa(ones, ones))
    assert gwet_ac1(ones, ones) == pytest.approx(1.0)

    rows = [Row(f"i{i}", "methods", "study001", "K", "K")
            for i in range(MIN_FIELD_N + 5)]
    (f,) = per_field(rows)
    assert f["degenerate"] is True
    assert f["reportable"] is True


def test_discriminating_field_is_not_flagged_degenerate():
    rows = [Row(f"i{i}", "methods", "study001",
                "K" if i % 4 == 0 else "D", "K" if i % 4 == 0 else "D")
            for i in range(MIN_FIELD_N + 5)]
    (f,) = per_field(rows)
    assert f["degenerate"] is False


def test_empty_input_returns_nan():
    e = np.array([], dtype=int)
    assert np.isnan(cohen_kappa(e, e))
    assert np.isnan(gwet_ac1(e, e))


@pytest.mark.parametrize("prevalence", [0.50, 0.26, 0.05])
def test_prevalence_paradox_is_why_both_are_reported(prevalence):
    """Observed agreement is held near constant; kappa falls, AC1 does not.

    At the corpus prevalence of roughly 0.26 the gap is already material, which
    is the justification for printing both coefficients rather than choosing.
    """
    rng = np.random.default_rng(7)
    n = 5000
    x = (rng.random(n) < prevalence).astype(int)
    y = np.where(rng.random(n) < 0.10, 1 - x, x)
    k, g = cohen_kappa(x, y), gwet_ac1(x, y)
    assert np.mean(x == y) == pytest.approx(0.90, abs=0.02)
    assert g >= k - 1e-9
    if prevalence == 0.05:
        assert g - k > 0.15


def test_bootstrap_brackets_the_point_estimate():
    a = np.array([1] * 30 + [0] * 70)
    b = np.array([1] * 20 + [0] * 10 + [1] * 10 + [0] * 60)
    lo, hi = bootstrap_ci(a, b, cohen_kappa)
    assert lo <= cohen_kappa(a, b) <= hi


def test_bootstrap_is_deterministic():
    a = np.array([1] * 30 + [0] * 70)
    b = np.array([1] * 20 + [0] * 10 + [1] * 10 + [0] * 60)
    assert bootstrap_ci(a, b, cohen_kappa) == bootstrap_ci(a, b, cohen_kappa)


def test_unsure_leaves_the_denominator():
    rows = [Row(f"i{i}", "methods", "study001", "K", "K") for i in range(60)]
    rows += [Row("u1", "methods", "study001", "K", "U"),
             Row("u2", "methods", "study001", "D", "U")]
    (f,) = per_field(rows)
    assert f["n_total"] == 62
    assert f["n_joint"] == 60
    assert f["n_unsure"] == 2


def test_thin_fields_get_no_coefficient():
    thin = [Row(f"t{i}", "random_seeds", "study001", "K", "K")
            for i in range(MIN_FIELD_N - 1)]
    fat = [Row(f"m{i}", "methods", "study001", "K" if i % 4 else "D",
               "K" if i % 4 else "D") for i in range(MIN_FIELD_N + 10)]
    res = {f["field"]: f for f in per_field(thin + fat)}
    assert res["random_seeds"]["reportable"] is False
    assert "kappa" not in res["random_seeds"]
    assert res["methods"]["reportable"] is True
    assert "kappa" in res["methods"]
