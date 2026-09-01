"""Tests for the multi-model Phase II pipeline wiring (no LLM, no Oxigraph).

Heavy dependencies (PDF chunking, embeddings, the LLM client, the triplestore,
and the rdflib mapper) are stubbed, so these tests check the multi-model
PLUMBING: model slugging, per-model graph scoping, model threading into the
extractor, and the persisted extraction artifact.
"""
import json
import sys
import types

# Stub the triplestore client before importing the pipeline (no Oxigraph /
# SPARQLWrapper needed); run() monkeypatches the graph fns anyway.
_ts = types.ModuleType("triplestore_client")
_ts.append_graph = lambda *a, **k: None
_ts.count_triples = lambda *a, **k: 0
_ts.graph_exists = lambda *a, **k: False
_ts.sparql_query = lambda q: {"boolean": False}
sys.modules["triplestore_client"] = _ts

import rag_pipeline.pipeline as pl  # noqa: E402


# ── model_slug ────────────────────────────────────────────────────────────────

def test_model_slug_basic():
    assert pl.model_slug("Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8") == \
        "qwen-qwen2-5-14b-instruct-gptq-int8"


def test_model_slug_handles_none_and_symbols():
    assert pl.model_slug(None) == "default"
    assert pl.model_slug("gpt-4o") == "gpt-4o"
    assert pl.model_slug("a__b//c") == "a-b-c"


# ── run() multi-model plumbing ────────────────────────────────────────────────

class _Store:
    def __init__(self, study_id): pass
    def is_built(self): return True
    def load(self): pass
    def build(self, chunks): pass
    def retrieve(self, query, top_k=3): return [f"passage::{query[:8]}"]


class _Extractor:
    """Records which model it was built for and returns fixed metadata."""
    def __init__(self, model): self.model = model
    def extract(self, passage):
        return {"random_seeds": [42],
                "evaluation_results": [{"metric": "acc", "value": "0.9",
                                        "split": "test"}]}


def _patch(monkeypatch, captured):
    monkeypatch.setattr(pl, "load_paper", lambda p, methods_only=True: ["chunk"])
    monkeypatch.setattr(pl, "EmbeddingStore", _Store)

    def fake_get_extractor(backend, model):
        captured["backend"], captured["model"] = backend, model
        return _Extractor(model)
    monkeypatch.setattr(pl, "get_extractor", fake_get_extractor)

    # mapper + triplestore stubbed (avoid rdflib + Oxigraph)
    monkeypatch.setattr(pl, "map_extraction", lambda sid, merged: ["t1", "t2"])
    monkeypatch.setattr(pl, "to_turtle", lambda g: "<turtle>")

    def fake_append(graph_uri, turtle):
        captured["graph_uri"] = graph_uri
    monkeypatch.setattr(pl, "append_graph", fake_append)
    monkeypatch.setattr(pl, "count_triples", lambda g: 99)


def test_run_scopes_graph_per_model(monkeypatch, tmp_path):
    captured = {}
    _patch(monkeypatch, captured)

    res = pl.run("study001", pdf_path="x.pdf",
                 backend="vllm", model="Qwen/Qwen2.5-14B",
                 extractions_dir=str(tmp_path))

    # a non-default model must land in a model-scoped graph
    assert res["graph_uri"] == \
        "https://w3id.org/rdip/graph/study001/ext/qwen-qwen2-5-14b"
    assert captured["graph_uri"] == res["graph_uri"]
    # the chosen model was threaded into the extractor
    assert captured["model"] == "Qwen/Qwen2.5-14B"
    assert res["model"] == "Qwen/Qwen2.5-14B"
    assert res["evals_found"] == 1
    assert res["triples_added"] == 2


def test_run_persists_extraction_json(monkeypatch, tmp_path):
    captured = {}
    _patch(monkeypatch, captured)

    res = pl.run("study007", pdf_path="x.pdf",
                 backend="vllm", model="gemma",
                 extractions_dir=str(tmp_path))

    jpath = tmp_path / "study007__gemma.json"
    assert jpath.exists()
    doc = json.loads(jpath.read_text())
    assert doc["study_id"] == "study007"
    assert doc["model"] == "gemma"
    assert doc["counts"]["random_seeds"] == 1
    assert doc["metadata"]["evaluation_results"][0]["metric"] == "acc"
    assert res["json_path"] == str(jpath)


def test_explicit_target_graph_overrides_scoping(monkeypatch, tmp_path):
    captured = {}
    _patch(monkeypatch, captured)

    # an explicit target_graph (e.g. merging the winning model into canonical)
    # bypasses the per-model scoping
    canonical = "https://w3id.org/rdip/graph/study003"
    res = pl.run("study003", pdf_path="x.pdf",
                 backend="vllm", model="gemma",
                 target_graph=canonical,
                 extractions_dir=str(tmp_path))
    assert res["graph_uri"] == canonical
    assert captured["graph_uri"] == canonical


# ── corpus runner: SRAF_MODELS parsing ────────────────────────────────────────

def test_parse_models_multi(monkeypatch):
    import rag_pipeline.run_corpus_extraction as rce
    monkeypatch.setenv(
        "SRAF_MODELS",
        "vllm:Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8, google:gemini-1.5-pro")
    assert rce.parse_models() == [
        ("vllm", "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8"),
        ("google", "gemini-1.5-pro"),
    ]


def test_parse_models_default(monkeypatch):
    import rag_pipeline.run_corpus_extraction as rce
    monkeypatch.delenv("SRAF_MODELS", raising=False)
    models = rce.parse_models()
    assert len(models) == 1   # falls back to configured backend/model
