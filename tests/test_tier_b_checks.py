"""Tests for the Tier-B reproducibility checks.

The placeholder detector is validated against the 13 extracted recipes whose
placeholder/concrete status is already established in
`analysis/taxonomy_restructured.md`, so these are regression tests against real
ground truth rather than invented examples.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build_harness"))

from tier_b_checks import (  # noqa: E402
    EVAL_HINT, find_placeholders, check_concrete_run_command,
    check_data_obtainable, check_documented_entrypoint,
    check_repo_matches_paper, run_tier_b,
    ABSENT, PARTIAL, FULL,
)

# Ground truth from the failure taxonomy (7 placeholder, 6 concrete).
PLACEHOLDER = {"study003", "study008", "study012", "study018",
               "study019", "study025", "study026"}
CONCRETE = {"study006", "study009", "study014", "study020", "study021", "study024"}


def _recipes():
    for f in sorted(glob.glob(str(ROOT / "data" / "recipes" / "study*.json"))):
        d = json.load(open(f))
        cmd = (d.get("run_command") or "").strip()
        if cmd:
            yield d["study_id"], cmd


@pytest.mark.parametrize("study_id,cmd", list(_recipes()))
def test_placeholder_detection_matches_taxonomy(study_id, cmd):
    """Every recipe must be classified as the taxonomy classified it."""
    expected_placeholder = study_id in PLACEHOLDER
    assert study_id in PLACEHOLDER or study_id in CONCRETE, "unlabelled recipe"
    assert bool(find_placeholders(cmd)) is expected_placeholder


def test_assigned_shell_var_is_not_a_placeholder():
    """`export NGPUS=8 && ... $NGPUS` is runnable exactly as written."""
    assert find_placeholders(
        "export NGPUS=8 && python -m torch.distributed.launch "
        "--nproc_per_node=$NGPUS train.py") == []


def test_unassigned_shell_var_is_a_placeholder():
    assert "$CONFIG" in find_placeholders("python tools/test.py $CONFIG")


def test_underscored_path_placeholder_is_caught():
    """Regression: `\\b` fails after `to` in `/path_to_maskrcnn_benchmark/`."""
    assert find_placeholders("python /path_to_maskrcnn_benchmark/tools/test.py")


@pytest.mark.parametrize("stem,expected", [
    ("eval_extraction", True),   # regression: \b fails before an underscore
    ("test.py", True),
    ("evaluate", True),
    ("latest", False),           # must not match a substring
    ("contest", False),
    ("run_all", False),
])
def test_eval_hint_word_boundaries(stem, expected):
    assert bool(EVAL_HINT.search(stem)) is expected


def test_concrete_command_prefers_a_run_over_setup(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Demo\n\n```\npip install -r requirements.txt\npython eval.py --split test\n```\n")
    r = check_concrete_run_command([(tmp_path / "README.md",
                                     (tmp_path / "README.md").read_text())])
    assert r.level == FULL
    assert "eval.py" in r.evidence


def test_placeholder_command_grades_partial(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Demo\n\n```\npython tools/test.py configs/a.py /path/to/checkpoint\n```\n")
    r = check_concrete_run_command([(tmp_path / "README.md",
                                     (tmp_path / "README.md").read_text())])
    assert r.level == PARTIAL


def test_no_command_grades_absent(tmp_path):
    (tmp_path / "README.md").write_text("# A paper\n\nSome prose, no commands.\n")
    r = check_concrete_run_command([(tmp_path / "README.md",
                                     (tmp_path / "README.md").read_text())])
    assert r.level == ABSENT


def test_gated_data_detected(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("Download the CSAW-M dataset. Access is granted upon request; "
                 "please fill out the form.\n")
    assert check_data_obtainable([(p, p.read_text())]).level == ABSENT


def test_ungated_data_passes(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("Download CIFAR-10 with `torchvision.datasets.CIFAR10`.\n")
    assert check_data_obtainable([(p, p.read_text())]).level == FULL


def test_repo_paper_mismatch_detected(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("# irc-url-title-bot\n\nPosts titles of URLs into IRC channels.\n")
    r = check_repo_matches_paper(
        [(p, p.read_text())],
        "Scaling Laws for Neural Language Models on Multimodal Corpora")
    assert r.level == ABSENT


def test_repo_paper_match_detected(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("# Scaling Laws for Neural Language Models\n\nOfficial code.\n")
    r = check_repo_matches_paper([(p, p.read_text())],
                                 "Scaling Laws for Neural Language Models")
    assert r.level == FULL


def test_no_paper_title_is_partial_not_a_failure(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("# anything\n")
    assert check_repo_matches_paper([(p, p.read_text())], None).level == PARTIAL


def test_run_tier_b_is_offline_by_default(tmp_path):
    (tmp_path / "README.md").write_text(
        "# x\n\nWeights: https://example.com/model.pth\n")
    out = run_tier_b(tmp_path)
    links = out["checks"]["links_resolve"]
    assert links["detail"]["checked"] is False
    assert out["tier_b_max"] == 10


def test_ci_and_unit_tests_are_not_an_evaluation_route(tmp_path):
    """Regression: microsoft/DeepSpeed matched 330 CI/test files as 'entrypoints'.

    A project's own test suite does not reproduce the paper's numbers.
    """
    (tmp_path / "README.md").write_text("# x\n\nNo commands here.\n")
    for rel in ("ci/test_tests_fetcher.py", "tests/test_model.py",
                ".github/test_ci.sh", "src/evaluator_test.py"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# noise\n")
    docs = [(tmp_path / "README.md", (tmp_path / "README.md").read_text())]
    assert check_documented_entrypoint(docs, tmp_path).level == ABSENT


def test_real_eval_script_still_found_and_ranked(tmp_path):
    (tmp_path / "README.md").write_text("# x\n\nNo commands here.\n")
    for rel in ("tests/test_model.py", "deep/nested/dir/evaluate.py",
                "tools/test.py"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# code\n")
    docs = [(tmp_path / "README.md", (tmp_path / "README.md").read_text())]
    r = check_documented_entrypoint(docs, tmp_path)
    assert r.level == PARTIAL
    assert "tools/test.py" in r.evidence      # conventional location wins
