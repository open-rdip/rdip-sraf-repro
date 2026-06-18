"""Unit tests for the RQ3 extraction evaluator (RDIP ground truth → repro fields)."""
import json

from evaluation.eval_extraction import (
    prf, field_counts, scalar_counts, evaluate_study, aggregate,
    _canon_value, _clean, names_match, normalize_gold, normalize_pred,
    PAPER_FIELDS, REPO_FIELDS, run,
)


# ── prf ───────────────────────────────────────────────────────────────────────

def test_prf_basic():
    m = prf(8, 2, 2)
    assert (m["precision"], m["recall"], m["f1"]) == (0.8, 0.8, 0.8)


# ── normalisation ─────────────────────────────────────────────────────────────

def test_clean_nullish_including_gold_phrasing():
    assert _clean("exact version not specified") is None
    assert _clean("1.13.1") == "1.13.1"


def test_canon_value_number_forms():
    assert _canon_value("0.94") == _canon_value("0.940") == _canon_value("94%")


# ── fuzzy name matching ───────────────────────────────────────────────────────

def test_acronym_match():
    assert names_match("RTN", "Round-to-nearest (RTN)")
    assert names_match("Camouflage-Aware Feature Refinement (CAFR)", "CAFR")


def test_surface_variant_match():
    assert names_match("CIFAR10", "CIFAR-10")
    assert names_match("VQ-VAE", "Vector Quantized Variational Autoencoder (VQ-VAE)")


def test_unrelated_names_dont_match():
    assert not names_match("ImageNet", "GLUE")
    assert not names_match("accuracy", "perplexity")


# ── exact vs fuzzy counts ─────────────────────────────────────────────────────

def test_methods_fuzzy_credits_acronym():
    gold = [{"name": "Round-to-nearest (RTN)"}]
    pred = [{"name": "RTN"}]
    assert field_counts("methods", gold, pred, strict=False, fuzzy=False) == (0, 1, 1)
    assert field_counts("methods", gold, pred, strict=False, fuzzy=True) == (1, 0, 0)


def test_software_strict_needs_version():
    gold = [{"name": "torch", "version": "1.13"}]
    pred = [{"name": "torch", "version": "2.0"}]
    assert field_counts("software", gold, pred, strict=False, fuzzy=False) == (1, 0, 0)
    assert field_counts("software", gold, pred, strict=True, fuzzy=False) == (0, 1, 1)


def test_eval_split_must_match_even_when_metric_does():
    gold = [{"metric": "acc", "value": "0.9", "split": "test"}]
    pred = [{"metric": "acc", "value": "0.9", "split": "val"}]
    assert field_counts("evaluation_results", gold, pred, False, True) == (0, 1, 1)


def test_scalar_counts_environment_fuzzy():
    g = {"gpu_model": "NVIDIA A100", "cuda_version": "11.7"}
    p = {"gpu_model": "A100", "cuda_version": "12.1"}
    # fuzzy credits the GPU surface variant (containment); cuda still differs
    assert scalar_counts(g, p, ("gpu_model", "cuda_version"), fuzzy=True) == (1, 1, 1)


# ── aggregate: grouping + N/A + headline ──────────────────────────────────────

def test_aggregate_marks_na_when_no_gold_support():
    gold = {"methods": [{"name": "bert"}], "parameters": [], "datasets": [],
            "evaluation_results": [], "environment": {},
            "software": [], "random_seeds": []}            # no seeds in gold
    pred = {"methods": [{"name": "bert"}], "parameters": [], "datasets": [],
            "evaluation_results": [], "environment": {},
            "software": [], "random_seeds": ["42"]}
    counts = evaluate_study(gold, pred)
    agg = aggregate({"s": counts})
    assert agg["per_field"]["random_seeds"]["na"] is True      # gold had none
    assert agg["per_field"]["methods"]["f1"] == 1.0
    assert agg["headline_micro"]["f1"] == 1.0                  # paper fields only


def test_headline_excludes_repo_fields():
    # perfect methods, terrible software → headline high, overall dragged down
    gold = {"methods": [{"name": "x"}], "parameters": [], "datasets": [],
            "evaluation_results": [], "environment": {},
            "software": [{"name": f"lib{i}"} for i in range(10)], "random_seeds": []}
    pred = {"methods": [{"name": "x"}], "parameters": [], "datasets": [],
            "evaluation_results": [], "environment": {},
            "software": [], "random_seeds": []}
    agg = aggregate({"s": evaluate_study(gold, pred)})
    assert agg["headline_micro"]["f1"] == 1.0
    assert agg["overall_micro"]["f1"] < 1.0
    assert "software" in REPO_FIELDS and "methods" in PAPER_FIELDS


# ── end-to-end ────────────────────────────────────────────────────────────────

def test_run_reads_tiered_layout(tmp_path):
    gt = tmp_path / "ground_truth" / "gold" / "study001"; gt.mkdir(parents=True)
    ext = tmp_path / "ext"; ext.mkdir()
    (gt / "gold_standard.json").write_text(json.dumps({"entities": {
        "Method": [{"name": "Round-to-nearest (RTN)"}],
        "SoftwareApplication": [], "Dataset": [], "Parameter": [],
        "RandomSeed": [], "ComputingEnvironment": [], "EvaluationResult": []}}))
    (ext / "study001__qwen.json").write_text(json.dumps({"metadata": {
        "methods": [{"name": "RTN"}], "dependencies": [], "datasets": [],
        "hyperparameters": [], "random_seeds": [], "hardware": {},
        "evaluation_results": []}}))
    # exact misses the acronym; fuzzy catches it
    assert run("qwen", str(ext), str(tmp_path / "ground_truth"), "gold",
               fuzzy=False)["per_field"]["methods"]["f1"] == 0.0
    assert run("qwen", str(ext), str(tmp_path / "ground_truth"), "gold",
               fuzzy=True)["per_field"]["methods"]["f1"] == 1.0


def test_compare_discovers_slugs(tmp_path):
    from evaluation.compare_models import discover_slugs
    ext = tmp_path / "ext"; ext.mkdir()
    (ext / "study001__good.json").write_text("{}")
    (ext / "study001__bad.json").write_text("{}")
    assert discover_slugs(str(ext)) == ["bad", "good"]
