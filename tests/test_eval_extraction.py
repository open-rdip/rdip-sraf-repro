"""Unit tests for the extraction precision/recall evaluator (RQ3)."""
import json

from evaluation.eval_extraction import (
    prf, list_counts, hardware_counts, evaluate_study, aggregate,
    _canon_value, LENIENT, STRICT, run,
)


# ── prf ───────────────────────────────────────────────────────────────────────

def test_prf_basic():
    m = prf(tp=8, fp=2, fn=2)
    assert m["precision"] == 0.8
    assert m["recall"] == 0.8
    assert m["f1"] == 0.8


def test_prf_zero_safe():
    assert prf(0, 0, 0)["f1"] == 0.0
    assert prf(0, 5, 0)["recall"] == 0.0


# ── value canonicalisation ────────────────────────────────────────────────────

def test_canon_value_equates_number_forms():
    assert _canon_value("0.94") == _canon_value("0.940")
    assert _canon_value("94%") == _canon_value("0.94")
    assert _canon_value("AdamW") == "adamw"


# ── list matching ─────────────────────────────────────────────────────────────

def test_list_counts_lenient_by_name():
    gold = [{"name": "pytorch", "version": "1.13"}, {"name": "numpy", "version": "1.24"}]
    pred = [{"name": "pytorch", "version": "2.0"},  {"name": "scipy", "version": "1.0"}]
    tp, fp, fn = list_counts(gold, pred, LENIENT["dependencies"])
    assert (tp, fp, fn) == (1, 1, 1)            # pytorch matched by name only


def test_list_counts_strict_needs_version():
    gold = [{"name": "pytorch", "version": "1.13"}]
    pred = [{"name": "pytorch", "version": "2.0"}]
    tp, fp, fn = list_counts(gold, pred, STRICT["dependencies"])
    assert (tp, fp, fn) == (0, 1, 1)            # version differs → no match


def test_list_counts_ignores_empty_keys():
    gold = [{"name": "pytorch"}, {"name": ""}]
    pred = [{"name": "pytorch"}]
    assert list_counts(gold, pred, LENIENT["dependencies"]) == (1, 0, 0)


def test_eval_results_keyed_on_metric_split():
    gold = [{"metric": "acc", "value": "0.9", "split": "test"}]
    pred = [{"metric": "acc", "value": "0.9", "split": "val"}]
    assert list_counts(gold, pred, LENIENT["evaluation_results"]) == (0, 1, 1)


# ── hardware ──────────────────────────────────────────────────────────────────

def test_hardware_counts():
    gold = {"gpu_model": "A100", "cuda_version": "11.7", "cpu_info": None}
    pred = {"gpu_model": "A100", "cuda_version": "12.1", "cpu_info": "Xeon"}
    tp, fp, fn = hardware_counts(gold, pred)
    assert tp == 1               # gpu match
    assert fp == 2               # cuda mismatch (counts as fp) + cpu hallucinated
    assert fn == 1               # cuda mismatch (counts as fn)


# ── study + aggregate ─────────────────────────────────────────────────────────

def test_evaluate_and_aggregate():
    gold = {"dependencies": [{"name": "pytorch"}], "random_seeds": [42],
            "hyperparameters": [], "datasets": [], "methods": [],
            "evaluation_results": [], "hardware": {}}
    pred = {"dependencies": [{"name": "pytorch"}], "random_seeds": [7],
            "hyperparameters": [], "datasets": [], "methods": [],
            "evaluation_results": [], "hardware": {}}
    counts = evaluate_study(gold, pred)
    assert counts["dependencies"] == (1, 0, 0)
    assert counts["random_seeds"] == (0, 1, 1)

    agg = aggregate({"study001": counts})
    assert agg["n_studies"] == 1
    assert agg["per_field_micro"]["dependencies"]["f1"] == 1.0
    assert agg["per_field_micro"]["random_seeds"]["f1"] == 0.0


def test_perfect_prediction_scores_one():
    gold = {"dependencies": [{"name": "numpy", "version": "1.24"}],
            "random_seeds": [1], "hyperparameters": [{"name": "lr", "value": "0.1"}],
            "datasets": [{"name": "glue"}], "methods": [{"name": "bert"}],
            "evaluation_results": [{"metric": "f1", "value": "0.9", "split": "test"}],
            "hardware": {"gpu_model": "A100"}}
    counts = evaluate_study(gold, gold, strict=True)
    agg = aggregate({"s": counts})
    assert agg["overall_micro"]["f1"] == 1.0
    assert agg["macro_f1"] == 1.0


# ── end-to-end via files ──────────────────────────────────────────────────────

def test_run_pairs_gold_with_extraction(tmp_path):
    gold_dir = tmp_path / "gold"; gold_dir.mkdir()
    ext_dir = tmp_path / "ext";   ext_dir.mkdir()

    (gold_dir / "study001.json").write_text(json.dumps({
        "metadata": {"dependencies": [{"name": "pytorch"}], "random_seeds": [42],
                     "hyperparameters": [], "datasets": [], "methods": [],
                     "evaluation_results": [], "hardware": {}}}))
    # a template file must be ignored
    (gold_dir / "study001.template.json").write_text("{}")
    (ext_dir / "study001__qwen.json").write_text(json.dumps({
        "model": "Qwen/X",
        "metadata": {"dependencies": [{"name": "pytorch"}], "random_seeds": [42],
                     "hyperparameters": [], "datasets": [], "methods": [],
                     "evaluation_results": [], "hardware": {}}}))

    rep = run("qwen", str(ext_dir), str(gold_dir))
    assert rep["n_studies"] == 1
    assert rep["overall_micro"]["f1"] == 1.0
    assert rep["skipped"] == []


def test_run_skips_studies_without_extraction(tmp_path):
    gold_dir = tmp_path / "gold"; gold_dir.mkdir()
    ext_dir = tmp_path / "ext";   ext_dir.mkdir()
    (gold_dir / "study009.json").write_text(json.dumps({"metadata": {}}))

    rep = run("qwen", str(ext_dir), str(gold_dir))
    assert rep["n_studies"] == 0
    assert rep["skipped"][0]["study"] == "study009"
