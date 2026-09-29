"""Tests for deterministic repository-side experimental fact extraction.

Behaviours locked in here were each found by running against real corpus
repositories (mmsegmentation), not invented.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build_harness"))

from repo_facts import (  # noqa: E402
    FACTS_VERSION, extract_repo_facts, find_datasets, find_hyperparameters,
    find_seeds, source_kind,
)


def _files(tmp_path, spec):
    out = []
    for rel, text in spec.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        out.append((p, text))
    return out


def test_readme_prose_is_not_a_repo_fact(tmp_path):
    """Regression: mmsegmentation's README mentions CIFAR-100 in a sentence about
    Transformers. A dataset named in prose is a mention, not something the
    repository uses, and must not drive a conflict."""
    files = _files(tmp_path, {
        "README.md": "While the Transformer architecture, unlike CIFAR-100 work, ...\n",
        "configs/seg/cityscapes.py": "dataset_type = 'CityscapesDataset'\n",
    })
    strong, weak = find_datasets(files)
    assert [d["canonical"] for d in strong] == ["Cityscapes"]
    assert [d["canonical"] for d in weak] == ["CIFAR-100"]


def test_config_evidence_outranks_a_prose_mention(tmp_path):
    files = _files(tmp_path, {
        "README.md": "We compare against COCO.\n",
        "configs/coco.py": "data_root = 'data/coco'\n",
    })
    strong, weak = find_datasets(files)
    assert [d["canonical"] for d in strong] == ["COCO"]
    assert weak == []


@pytest.mark.parametrize("line", [
    "optimizer = optimizer",                       # key echoing its own name
    "num_classes = model.decode_head.num_classes",  # attribute reference
    "lr = get_lr()",                               # call
    "batch_size = None",
])
def test_non_values_are_rejected(tmp_path, line):
    files = _files(tmp_path, {"configs/a.py": line + "\n"})
    assert find_hyperparameters(files) == []


def test_real_hyperparameter_values_are_kept(tmp_path):
    files = _files(tmp_path, {"configs/a.py": "lr = 0.02\nbatch_size = 4\nepochs = 80\n"})
    got = {h["canonical"]: h["value"] for h in find_hyperparameters(files)}
    assert got == {"learning_rate": "0.02", "batch_size": "4", "epochs": "80"}


def test_alias_folding(tmp_path):
    """CIFAR-100, cifar100 and CIFAR_100 must fold to one canonical name."""
    files = _files(tmp_path, {"configs/a.py": "d1='CIFAR-100'\nd2='cifar100'\nd3='CIFAR_100'\n"})
    strong, _ = find_datasets(files)
    assert [d["canonical"] for d in strong] == ["CIFAR-100"]


def test_argparse_defaults_are_read_without_executing(tmp_path):
    files = _files(tmp_path, {
        "train.py": "import argparse\np=argparse.ArgumentParser()\n"
                    "p.add_argument('--lr', default=0.1)\n"
                    "p.add_argument('--batch-size', default=32)\n"})
    got = {h["canonical"]: h["value"] for h in find_hyperparameters(files)}
    assert got.get("learning_rate") == "0.1"


@pytest.mark.parametrize("snippet,expected", [
    ("torch.manual_seed(42)", "42"),
    ("seed = 1234", "1234"),
    ("pl.seed_everything(7)", "7"),
    ("python train.py --seed 99", "99"),
])
def test_seed_forms(tmp_path, snippet, expected):
    files = _files(tmp_path, {"tools/train.py": snippet + "\n"})
    assert [s["value"] for s in find_seeds(files)] == [expected]


def test_source_kind_classification(tmp_path):
    assert source_kind(Path("configs/a.py")) == "config"
    assert source_kind(Path("a.yaml")) == "config"
    assert source_kind(Path("README.md")) == "docs"
    assert source_kind(Path("docs/guide.rst")) == "docs"


def test_extract_carries_a_version_stamp(tmp_path):
    (tmp_path / "README.md").write_text("# x\n")
    out = extract_repo_facts(tmp_path)
    assert out["facts_version"] == FACTS_VERSION
    for k in ("datasets", "hyperparameters", "metrics", "seeds",
              "dataset_mentions_docs_only"):
        assert k in out


@pytest.mark.parametrize("text,expected", [
    ("dataset_type = 'CityscapesDataset'", ["Cityscapes"]),   # mm-family convention
    ("dataset_type = 'CocoDataset'", ["COCO"]),
    ("from x import CIFAR100Dataset", ["CIFAR-100"]),
    ("word = 'VOCabulary'", []),            # lowercase suffix is NOT a boundary
    ("n = 'cifar100k'", []),
])
def test_camelcase_suffix_is_a_boundary_but_lowercase_is_not(tmp_path, text, expected):
    files = _files(tmp_path, {"configs/a.py": text + "\n"})
    strong, _ = find_datasets(files)
    assert [d["canonical"] for d in strong] == expected


# ── Boundary: CamelCase opens a new word, an acronym run does not ─────────────
#
# Found on study080 (real-stanford/cow): the alias "vg" fired inside the string
# "VGA compatible controller" in a GPU-detection routine and Visual Genome was
# recorded as a dataset the repository uses. The right-hand boundary has to
# admit CocoDataset while rejecting VGA, which is why it tests for an uppercase
# letter followed by a lowercase one rather than for any uppercase letter.

@pytest.mark.parametrize("text,expected", [
    ('and r["Class"] in ["VGA compatible controller"]', []),
    ("coverage is ADEQUATE for now", []),
    ("VOCAB size is 30000", []),
    ('parser.add_argument("--vg", default="VG")', ["Visual Genome"]),
])
def test_acronym_continuation_is_not_a_boundary(tmp_path, text, expected):
    files = _files(tmp_path, {"configs/a.py": text + "\n"})
    strong, _ = find_datasets(files)
    assert [d["canonical"] for d in strong] == expected


# ── Python prose is not a repository fact ────────────────────────────────────
#
# Also from study080: COCO was recorded as a dataset because a docstring in
# clip_owl.py described converting OwlViT output to COCO format. The file is
# .py so source_kind calls it config, but a docstring is prose in exactly the
# way a README is. Comments likewise. Ordinary string literals must survive,
# because default="prompt_templates/imagenet_templates.py" IS a real fact.

def test_docstrings_and_comments_are_not_config_facts(tmp_path):
    src = (
        '"""\n'
        'Converts the output to COCO format for evaluation.\n'
        '"""\n'
        'import os  # cifar10 is also supported\n'
        'TEMPLATES = "prompt_templates/imagenet_templates.py"\n'
    )
    files = _files(tmp_path, {"configs/clip_owl.py": src})
    strong, _ = find_datasets(files)
    found = {d["canonical"] for d in strong}
    assert "COCO" not in found, "a docstring mention must not become a config fact"
    assert "CIFAR-10" not in found, "a # comment must not become a config fact"
    assert "ImageNet" in found, "a real config string literal must survive"


def test_stripping_preserves_line_numbers(tmp_path):
    """Evidence strings carry a line number, so the stripper blanks rather than
    deletes — otherwise every fact after a docstring cites the wrong line."""
    from repo_facts import strip_python_prose
    src = '"""\na\nb\n"""\nSEED = 7\n'
    assert strip_python_prose(src).count("\n") == src.count("\n")
    files = _files(tmp_path, {"configs/c.py": src})
    seeds = find_seeds(files)
    assert seeds and seeds[0]["evidence"].endswith(":5")


def test_facts_version_is_stamped_on_output(tmp_path):
    """The corpus sweep skips or re-runs a study by comparing this stamp, so a
    behaviour change that does not bump it silently mixes extractor versions."""
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "a.py").write_text("lr = 3e-4\n")
    assert extract_repo_facts(tmp_path)["facts_version"] == FACTS_VERSION


# ── Metrics the repository can COMPUTE ───────────────────────────────────────
#
# The original finder only recognised --eval/--metric flags, so five of the
# first six corpus studies reported zero metrics — not enough to decide
# `metric_never_computed`. Each signal below is structurally anchored; a bare
# keyword sweep would match the word "accuracy" in any README.

from repo_facts import find_metrics, METRIC_SIGNAL_RANK  # noqa: E402


@pytest.mark.parametrize("fname,text,canonical,signal", [
    ("configs/a.py", "from sklearn.metrics import f1_score\ns = f1_score(y, p)\n",
     "F1", "metric_api"),
    ("configs/b.py", "val_evaluator = dict(type='CocoMetric')\n",
     "mAP", "metric_api"),
    ("configs/c.py", 'm = evaluate.load("rouge")\n', "ROUGE", "metric_api"),
    ("configs/d.py", "evaluation = dict(metric=['mIoU'])\n", "mIoU", "eval_config"),
    ("README.md", "python test.py --eval bbox\n", "mAP", "cli_flag"),
    ("configs/e.py", 'writer.add_scalar("val/psnr", v)\n', "PSNR", "logged"),
    ("configs/f.py", 'print(results["top1"])\n', "Top-1 accuracy", "logged"),
])
def test_each_metric_signal_is_detected(tmp_path, fname, text, canonical, signal):
    found = find_metrics(_files(tmp_path, {fname: text}))
    by_canon = {m["canonical"]: m for m in found}
    assert canonical in by_canon, f"{canonical} not found in {list(by_canon)}"
    assert by_canon[canonical]["signal"] == signal


def test_a_metric_list_yields_every_element(tmp_path):
    """`metric=['bbox','segm']` is the standard detection setting; capturing
    only the first quoted item silently dropped mask AP."""
    found = find_metrics(_files(
        tmp_path, {"configs/a.py": "evaluation = dict(metric=['mIoU','mDice','mAcc'])\n"}))
    assert {m["canonical"] for m in found} == {"mIoU", "mDice", "mAcc"}


def test_stronger_signal_wins_for_the_same_metric(tmp_path):
    """A library call is better evidence that the code computes a metric than a
    name appearing in a log line, so the record must keep the call."""
    found = find_metrics(_files(tmp_path, {
        "configs/log.py": 'wandb.log({"val/f1": f})\n',
        "configs/run.py": "from sklearn.metrics import f1_score\nf1_score(a, b)\n",
    }))
    f1 = [m for m in found if m["canonical"] == "F1"]
    assert len(f1) == 1 and f1[0]["signal"] == "metric_api"
    assert METRIC_SIGNAL_RANK["metric_api"] > METRIC_SIGNAL_RANK["logged"]


def test_prose_mentions_do_not_count_as_computable(tmp_path):
    """A paper-style sentence in a docstring names metrics the code may never
    compute. That distinction is the whole point of metric_never_computed."""
    src = ('"""We report accuracy, mIoU and BLEU in Table 2."""\n'
           "# f1_score would also be nice\n"
           "x = 1\n")
    assert find_metrics(_files(tmp_path, {"configs/a.py": src})) == []
