"""Unit tests for the FAIR-R calibration metrics (pure, no KG / no scipy)."""
import math

from calibration.run_calibration import (
    pairwise_concordance,
    band_summary,
    separation,
    BAND_ORDINAL,
)

HIGH = BAND_ORDINAL["high"]
LOW = BAND_ORDINAL["low"]
MID = BAND_ORDINAL["mid"]


def test_perfect_ranking_is_one():
    # every high scores above every low
    items = [(HIGH, 80), (HIGH, 70), (LOW, 30), (LOW, 20)]
    assert pairwise_concordance(items) == 1.0


def test_inverted_ranking_is_zero():
    items = [(HIGH, 10), (HIGH, 20), (LOW, 80), (LOW, 90)]
    assert pairwise_concordance(items) == 0.0


def test_same_band_pairs_ignored():
    # only the cross-band pair counts; the within-high pair must not.
    items = [(HIGH, 50), (HIGH, 90), (LOW, 40)]
    assert pairwise_concordance(items) == 1.0


def test_score_tie_across_bands_is_half():
    items = [(HIGH, 50), (LOW, 50)]
    assert pairwise_concordance(items) == 0.5


def test_no_cross_band_pairs_is_nan():
    assert math.isnan(pairwise_concordance([(HIGH, 10), (HIGH, 20)]))


def test_three_band_monotonic():
    items = [(HIGH, 90), (MID, 60), (LOW, 30)]
    assert pairwise_concordance(items) == 1.0


def test_separation_positive_when_clean():
    items = [(HIGH, 70), (HIGH, 80), (LOW, 30), (LOW, 55)]
    assert separation(items) == 15.0      # min(high)=70 - max(low)=55


def test_separation_negative_on_overlap():
    items = [(HIGH, 40), (LOW, 60)]
    assert separation(items) == -20.0


def test_separation_none_without_both_bands():
    assert separation([(HIGH, 70), (HIGH, 80)]) is None


def test_band_summary_stats():
    items = [(HIGH, 80), (HIGH, 60), (LOW, 20)]
    s = band_summary(items)
    assert s["high"] == {"n": 2, "mean": 70.0, "min": 60.0, "max": 80.0}
    assert s["low"] == {"n": 1, "mean": 20.0, "min": 20.0, "max": 20.0}
