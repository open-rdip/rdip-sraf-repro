"""Tests for the RAG extraction -> RDIP mapper (datasets + evaluation results)."""
import pytest

rdflib = pytest.importorskip("rdflib")
from rag_pipeline.mapper import map_extraction  # noqa: E402

RDIP = rdflib.Namespace("https://w3id.org/rdip/")
DCAT = rdflib.Namespace("http://www.w3.org/ns/dcat#")
RDF = rdflib.RDF


def _g(ext):
    base = {"random_seeds": [], "hyperparameters": [], "methods": [],
            "datasets": [], "dependencies": [], "hardware": {},
            "evaluation_results": []}
    base.update(ext)
    return map_extraction("s1", base)


def _count(g, p, o=None):
    return len(list(g.triples((None, p, o)))) if o is None else \
        len(list(g.triples((None, p, o))))


def test_dataset_typed_as_dcat():
    g = _g({"datasets": [{"name": "GLUE", "version": "1.0"}]})
    assert len(list(g.triples((None, RDF.type, DCAT.Dataset)))) == 1
    assert len(list(g.triples((None, RDIP.usedDataset, None)))) == 1


def test_evaluation_result_node():
    g = _g({"evaluation_results": [{"metric": "accuracy", "value": "0.9432", "split": "test"}]})
    assert len(list(g.triples((None, RDF.type, RDIP.EvaluationResult)))) == 1
    assert len(list(g.triples((None, RDIP.generatesResult, None)))) == 1
    assert len(list(g.triples((None, RDIP.metricName, None)))) == 1
    assert len(list(g.triples((None, RDIP.metricValue, None)))) == 1
    assert len(list(g.triples((None, RDIP.splitLabel, None)))) == 1


def test_evaluation_result_skips_missing_metric():
    g = _g({"evaluation_results": [{"value": "0.9"}]})    # no metric -> skipped
    assert len(list(g.triples((None, RDF.type, RDIP.EvaluationResult)))) == 0


def test_seeds_and_methods():
    g = _g({"random_seeds": [42], "methods": [{"name": "ZeroQuant", "description": "PTQ"}]})
    assert len(list(g.triples((None, RDF.type, RDIP.RandomSeed)))) == 1
    assert len(list(g.triples((None, RDIP.usedMethod, None)))) == 1
