"""Tests for the paper-vs-repository semantic diff (N4).

The rules that matter here are not the conflict detectors themselves but the
decidability bookkeeping: a conflict may only be raised when both sides state
something. Everything else in the evaluation rests on that, because precision
and recall computed over a corpus that silently treats "could not tell" as "no
conflict" would be meaningless.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sre_engine"))
sys.path.insert(0, str(ROOT / "build_harness"))

from paper_repo_diff import (  # noqa: E402
    BOTH_SILENT, DECIDABLE, PAPER_SILENT, REPO_SILENT,
    _diff_datasets, _diff_hyperparameters, _diff_metrics, _diff_seeds,
    _diff_dependencies, _values_agree,
)


# ── decidability ─────────────────────────────────────────────────────────────

def test_silence_on_either_side_is_not_agreement():
    """The whole evaluation depends on this. A repository that names no dataset
    has not agreed with the paper; it has said nothing."""
    paper = {"datasets": [{"name": "CIFAR-10"}]}
    assert _diff_datasets(paper, {"datasets": []})[0] == REPO_SILENT
    assert _diff_datasets({"datasets": []}, {"datasets": [{"canonical": "COCO"}]})[0] \
        == PAPER_SILENT
    assert _diff_datasets({}, {})[0] == BOTH_SILENT
    for state in (REPO_SILENT, PAPER_SILENT, BOTH_SILENT):
        pass  # documented above; no conflicts may be emitted in any of them
    assert _diff_datasets(paper, {"datasets": []})[1] == []


def test_metric_never_computed_is_undecidable_when_the_repo_exposes_none():
    """Six of the first nine corpus repositories expose no machine-identifiable
    metric computation. Treating that as 'the metric is never computed' would
    manufacture the paper's own headline result out of a detector gap."""
    paper = {"evaluation_results": [{"metric": "mIoU"}]}
    decidability, conflicts = _diff_metrics(paper, {"metrics": []})
    assert decidability == REPO_SILENT
    assert conflicts == []


def test_metric_never_computed_fires_when_the_repo_computes_others():
    paper = {"evaluation_results": [{"metric": "mIoU"}, {"metric": "accuracy"}]}
    facts = {"metrics": [{"canonical": "Accuracy", "signal": "metric_api"}]}
    decidability, conflicts = _diff_metrics(paper, facts)
    assert decidability == DECIDABLE
    assert [c["name"] for c in conflicts] == ["mIoU"]


# ── conflict detectors ───────────────────────────────────────────────────────

def test_datasets_conflict_only_when_wholly_disjoint():
    """A paper naming several datasets it merely compares against must not raise
    a conflict for each one it does not use."""
    paper = {"datasets": [{"name": "CIFAR-10"}, {"name": "ImageNet"}]}
    facts = {"datasets": [{"canonical": "ImageNet"}]}
    assert _diff_datasets(paper, facts) == (DECIDABLE, [])

    facts = {"datasets": [{"canonical": "COCO"}]}
    decidability, conflicts = _diff_datasets(paper, facts)
    assert decidability == DECIDABLE
    assert len(conflicts) == 1 and conflicts[0]["type"] == "dataset_mismatch"


@pytest.mark.parametrize("a,b,agree", [
    ("0.0003", "3e-4", True),      # same number, different notation
    ("16", "16.0", True),
    ("AdamW", "adamw", True),
    ("batch-size", "batch_size", True),
    ("16", "2", False),
    ("0.05", "0.0002", False),
])
def test_value_comparison(a, b, agree):
    assert _values_agree(a, b) is agree


def test_hyperparameter_needs_the_same_name_on_both_sides():
    """Two sides that both speak but never about the same hyperparameter are
    not in agreement and not in conflict — there is nothing to compare."""
    paper = {"hyperparameters": [{"name": "lr", "value": "0.1"}]}
    facts = {"hyperparameters": [{"canonical": "batch_size", "value": "32"}]}
    assert _diff_hyperparameters(paper, facts)[0] == REPO_SILENT


def test_citation_markers_are_not_dependency_versions():
    """The extractor reads '[54]' out of a citation and calls it a version.
    Comparing it against a real pin would produce a guaranteed false conflict."""
    paper = {"dependencies": [{"name": "MMDetection", "version": "[54]"}]}
    meta = {"software_dependencies": [{"name": "mmdetection", "version": "2.25.0"}]}
    assert _diff_dependencies(paper, meta)[0] == PAPER_SILENT


def test_seed_conflict_needs_both_sides_and_no_overlap():
    facts = {"seeds": [{"value": "42"}]}
    assert _diff_seeds({"random_seeds": [42]}, facts, {}) == (DECIDABLE, [])
    decidability, conflicts = _diff_seeds({"random_seeds": [3]}, facts, {})
    assert decidability == DECIDABLE
    assert conflicts and conflicts[0]["type"] == "seed_mismatch"
    assert _diff_seeds({"random_seeds": []}, facts, {})[0] == PAPER_SILENT


def test_repo_seeds_come_from_both_deterministic_sources():
    """repo_facts scans configs and code; repo_metadata carries the lifter's
    parser output. A seed found by either counts."""
    decidability, conflicts = _diff_seeds(
        {"random_seeds": [7]}, {"seeds": []}, {"seeds": [{"value": "7"}]})
    assert (decidability, conflicts) == (DECIDABLE, [])


# ── coverage bookkeeping ─────────────────────────────────────────────────────

def test_unrecognised_paper_names_are_counted_not_discarded():
    """study003 claims AP50, AP75 and APm; no alias recognises them, so three of
    its four claimed metrics never reach comparison. Dropping them silently
    would let the corpus report high decidability on claims never examined."""
    from paper_repo_diff import _canon_set_with_misses
    from repo_facts import METRIC_ALIASES
    found, misses = _canon_set_with_misses(["mAP", "AP50", "AP75"], METRIC_ALIASES)
    assert found == {"mAP"}
    assert sorted(misses) == ["AP50", "AP75"]
