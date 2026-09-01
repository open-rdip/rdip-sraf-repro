"""Unit tests for the result-reproducibility comparison (RQ #20)."""
from result_repro.compare_results import (
    _num, classify_pair, compare_entry, summarize,
)


def test_num_parses_forms():
    assert _num("10.90") == 10.9
    assert _num("94%") == 0.94
    assert _num("1,024") == 1024.0
    assert _num("n/a") is None


def test_classify_within_tolerance():
    assert classify_pair("10.90", "10.92") == "reproduced"      # <5%
    assert classify_pair("0.943", "0.945") == "reproduced"      # abs <0.01
    assert classify_pair("70.5", "40.0") == "mismatch"


def test_classify_percent_vs_fraction():
    assert classify_pair("94%", "0.94") == "reproduced"


def test_entry_reproduced_partial_mismatch():
    base = {"study_id": "s", "claimed": [
        {"metric": "acc", "claimed": "0.90", "split": "test"},
        {"metric": "F1", "claimed": "0.80", "split": "test"}]}

    rep = compare_entry({**base, "obtained": [
        {"metric": "accuracy", "value": "0.91", "split": "test"},
        {"metric": "F1", "value": "0.79", "split": "test"}]})
    assert rep["status"] == "reproduced"          # fuzzy acc↔accuracy, both within tol

    par = compare_entry({**base, "obtained": [
        {"metric": "acc", "value": "0.90", "split": "test"},
        {"metric": "F1", "value": "0.40", "split": "test"}]})
    assert par["status"] == "partial"

    mis = compare_entry({**base, "obtained": [
        {"metric": "acc", "value": "0.10", "split": "test"}]})
    assert mis["status"] == "mismatch"


def test_entry_run_failed_and_skipped():
    assert compare_entry({"study_id": "s", "claimed": [{"metric": "a", "claimed": "1"}],
                          "obtained": []})["status"] == "run_failed"
    assert compare_entry({"study_id": "s", "status": "skipped",
                          "claimed": [], "obtained": []})["status"] == "skipped"


def test_summarize_counts_and_rate():
    entries = [
        {"study_id": "a", "claimed": [{"metric": "acc", "claimed": "0.9"}],
         "obtained": [{"metric": "acc", "value": "0.9"}]},          # reproduced
        {"study_id": "b", "claimed": [{"metric": "acc", "claimed": "0.9"}],
         "obtained": [{"metric": "acc", "value": "0.1"}]},          # mismatch
        {"study_id": "c", "claimed": [{"metric": "acc", "claimed": "0.9"}],
         "obtained": []},                                            # run_failed
    ]
    s = summarize(entries)
    assert s["status_counts"]["reproduced"] == 1
    assert s["status_counts"]["mismatch"] == 1
    assert s["status_counts"]["run_failed"] == 1
    assert s["n_ran"] == 2
    assert s["reproduced_rate_of_ran"] == 0.5
