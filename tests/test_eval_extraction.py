"""Unit tests for the RQ3 extraction evaluator (RDIP ground truth → repro fields)."""
import json

from evaluation.eval_extraction import (
    prf, list_counts, scalar_counts, evaluate_study, aggregate,
    _canon_value, _clean, normalize_gold, normalize_pred,
    LENIENT, STRICT, run,
)


# ── prf ───────────────────────────────────────────────────────────────────────

def test_prf_basic():
    m = prf(tp=8, fp=2, fn=2)
    assert (m["precision"], m["recall"], m["f1"]) == (0.8, 0.8, 0.8)


def test_prf_zero_safe():
    assert prf(0, 0, 0)["f1"] == 0.0


# ── normalisation ─────────────────────────────────────────────────────────────

def test_clean_nullish_including_gold_phrasing():
    assert _clean("exact version not specified") is None
    assert _clean("N/A") is None
    assert _clean("1.13.1") == "1.13.1"


def test_canon_value_number_forms():
    assert _canon_value("0.94") == _canon_value("0.940") == _canon_value("94%")


def test_normalize_gold_maps_rdip_entities():
    doc = {"entities": {
        "SoftwareApplication": [{"name": "PyTorch", "version": "exact version not specified"}],
        "Dataset": [{"name": "GLUE"}],
        "Method": [{"name": "BERT"}],
        "Parameter": [{"name": "lr", "value": "3e-4"}],
        "RandomSeed": [{"name": "random_seed", "value": "42", "source": "repo"}],
        "ComputingEnvironment": [{"os": "Ubuntu", "gpu": "A100", "cuda": "11.7", "ram": "null"}],
        "EvaluationResult": [{"metric": "acc", "value": "0.9", "split": "test", "dataset": "GLUE"}],
        "Person": [{"name": "X"}], "Organization": [{"name": "Y"}], "Activity": [],
    }}
    g = normalize_gold(doc)
    assert g["software"] == [{"name": "PyTorch", "version": None}]   # nullish version cleaned
    assert g["random_seeds"] == ["42"]
    assert g["environment"] == {"gpu_model": "A100", "cuda_version": "11.7"}
    assert g["parameters"][0]["value"] == "3e-4"
    # Person/Organization/Activity are intentionally dropped
    assert set(g.keys()) == {"software", "datasets", "methods", "parameters",
                             "random_seeds", "environment", "evaluation_results"}


def test_normalize_pred_maps_pipeline_output():
    doc = {"metadata": {
        "dependencies": [{"name": "torch", "version": "2.0"}],
        "datasets": [{"name": "glue"}], "methods": [{"name": "bert", "description": "x"}],
        "hyperparameters": [{"name": "lr", "value": "0.0003"}],
        "random_seeds": [42],
        "hardware": {"gpu_model": "A100", "cuda_version": "12.1", "cpu_info": None},
        "evaluation_results": [{"metric": "acc", "value": "90%", "split": "test"}],
    }}
    p = normalize_pred(doc)
    assert p["software"] == [{"name": "torch", "version": "2.0"}]
    assert p["random_seeds"] == ["42"]
    assert p["environment"] == {"gpu_model": "A100", "cuda_version": "12.1"}


# ── matching ──────────────────────────────────────────────────────────────────

def test_list_counts_lenient_vs_strict_software():
    gold = [{"name": "torch", "version": "1.13"}]
    pred = [{"name": "torch", "version": "2.0"}]
    assert list_counts(gold, pred, LENIENT["software"]) == (1, 0, 0)   # name match
    assert list_counts(gold, pred, STRICT["software"]) == (0, 1, 1)    # version differs


def test_eval_results_metric_value_split():
    gold = [{"metric": "acc", "value": "0.9", "split": "test"}]
    pred = [{"metric": "acc", "value": "90%", "split": "test"}]
    assert list_counts(gold, pred, STRICT["evaluation_results"]) == (1, 0, 0)  # 90%==0.9


def test_scalar_counts_environment():
    g = {"gpu_model": "A100", "cuda_version": "11.7"}
    p = {"gpu_model": "A100", "cuda_version": "12.1"}
    assert scalar_counts(g, p, ("gpu_model", "cuda_version")) == (1, 1, 1)


# ── study + aggregate ─────────────────────────────────────────────────────────

def test_perfect_self_match_scores_one():
    doc = {"entities": {
        "SoftwareApplication": [{"name": "torch", "version": "2.0"}],
        "Dataset": [{"name": "glue"}], "Method": [{"name": "bert"}],
        "Parameter": [{"name": "lr", "value": "0.1"}],
        "RandomSeed": [{"value": "1"}],
        "ComputingEnvironment": [{"gpu": "A100", "cuda": "12.1"}],
        "EvaluationResult": [{"metric": "f1", "value": "0.9", "split": "test"}],
    }}
    g = normalize_gold(doc)
    counts = evaluate_study(g, g, strict=True)
    agg = aggregate({"s": counts})
    assert agg["overall_micro"]["f1"] == 1.0
    assert agg["macro_f1"] == 1.0


def test_aggregate_mixes_fields():
    gold = {"software": [{"name": "torch"}], "datasets": [], "methods": [],
            "parameters": [], "random_seeds": ["42"], "evaluation_results": [],
            "environment": {}}
    pred = {"software": [{"name": "torch"}], "datasets": [], "methods": [],
            "parameters": [], "random_seeds": ["7"], "evaluation_results": [],
            "environment": {}}
    counts = evaluate_study(gold, pred)
    assert counts["software"] == (1, 0, 0)
    assert counts["random_seeds"] == (0, 1, 1)


# ── end-to-end against the real directory layout ──────────────────────────────

def test_run_reads_tiered_layout(tmp_path):
    gt = tmp_path / "ground_truth" / "gold" / "study001"; gt.mkdir(parents=True)
    ext = tmp_path / "ext"; ext.mkdir()
    (gt / "gold_standard.json").write_text(json.dumps({"entities": {
        "SoftwareApplication": [{"name": "torch", "version": "2.0"}],
        "Dataset": [], "Method": [], "Parameter": [], "RandomSeed": [],
        "ComputingEnvironment": [], "EvaluationResult": []}}))
    (ext / "study001__qwen.json").write_text(json.dumps({"metadata": {
        "dependencies": [{"name": "torch", "version": "2.0"}],
        "datasets": [], "methods": [], "hyperparameters": [], "random_seeds": [],
        "hardware": {}, "evaluation_results": []}}))

    rep = run("qwen", str(ext), str(tmp_path / "ground_truth"), tier="gold")
    assert rep["n_studies"] == 1
    assert rep["per_field_micro"]["software"]["f1"] == 1.0
    assert rep["skipped"] == []


def test_run_skips_missing_extraction(tmp_path):
    gt = tmp_path / "ground_truth" / "silver" / "study009"; gt.mkdir(parents=True)
    (gt / "gold_standard.json").write_text(json.dumps({"entities": {}}))
    rep = run("qwen", str(tmp_path / "ext_missing"),
              str(tmp_path / "ground_truth"), tier="silver")
    assert rep["n_studies"] == 0
    assert rep["skipped"][0]["study"] == "study009"


# ── compare_models driver ─────────────────────────────────────────────────────

def test_compare_discovers_slugs_and_tabulates(tmp_path):
    from evaluation.compare_models import discover_slugs, compare
    gt = tmp_path / "ground_truth" / "gold" / "study001"; gt.mkdir(parents=True)
    ext = tmp_path / "ext"; ext.mkdir()
    (gt / "gold_standard.json").write_text(json.dumps({"entities": {
        "SoftwareApplication": [{"name": "torch"}], "Dataset": [], "Method": [],
        "Parameter": [], "RandomSeed": [], "ComputingEnvironment": [],
        "EvaluationResult": []}}))
    # two models: one correct, one wrong
    (ext / "study001__good.json").write_text(json.dumps({"metadata": {
        "dependencies": [{"name": "torch"}], "datasets": [], "methods": [],
        "hyperparameters": [], "random_seeds": [], "hardware": {},
        "evaluation_results": []}}))
    (ext / "study001__bad.json").write_text(json.dumps({"metadata": {
        "dependencies": [{"name": "tensorflow"}], "datasets": [], "methods": [],
        "hyperparameters": [], "random_seeds": [], "hardware": {},
        "evaluation_results": []}}))

    assert discover_slugs(str(ext)) == ["bad", "good"]
    cmp = compare(["good", "bad"], str(ext), str(tmp_path / "ground_truth"), "gold")
    assert cmp["reports"]["good"]["per_field_micro"]["software"]["f1"] == 1.0
    assert cmp["reports"]["bad"]["per_field_micro"]["software"]["f1"] == 0.0
