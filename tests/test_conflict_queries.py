"""Unit tests for the four semantic-diff CONSTRUCT queries.

Validates the SPARQL logic against synthetic named graphs (the layer where the
hardcoded-URI and FILTER-scope bugs lived). Uses arbitrary graph URIs so a
regression to hardcoded study001/002 would fail here.
"""
import pytest

rdflib = pytest.importorskip("rdflib")
from rdflib import Dataset, Namespace, Literal, URIRef, RDF  # noqa: E402
from pathlib import Path  # noqa: E402

RDIP = Namespace("https://w3id.org/rdip/")
EX = Namespace("http://ex/")
O = "https://w3id.org/rdip/graph/study042"   # deliberately NOT study001/002
R = "https://w3id.org/rdip/graph/study099"
SPARQL = Path(__file__).resolve().parent.parent / "sre_engine" / "sparql"


def _run(fn, ds):
    q = (SPARQL / fn).read_text()
    q = q.replace("GRAPH ?originalGraph", f"GRAPH <{O}>").replace(
        "GRAPH ?reproductionGraph", f"GRAPH <{R}>")
    q = "\n".join(l for l in q.splitlines()
                  if "?originalGraph" not in l and "?reproductionGraph" not in l)
    res = ds.query(q)
    types = {str(o) for s, p, o in res if p == RDF.type}
    return types


def _ds():
    ds = Dataset()
    return ds, ds.graph(URIRef(O)), ds.graph(URIRef(R))


def test_version_conflict_detected():
    ds, g1, g2 = _ds()
    g1.add((EX.s1, RDIP.softwareDependency, EX.d1)); g1.add((EX.d1, RDIP.dependencyName, Literal("torch"))); g1.add((EX.d1, RDIP.dependencyVersion, Literal("1.12.0")))
    g2.add((EX.s2, RDIP.softwareDependency, EX.d2)); g2.add((EX.d2, RDIP.dependencyName, Literal("torch"))); g2.add((EX.d2, RDIP.dependencyVersion, Literal("2.0.0")))
    assert str(RDIP.VersionConflict) in _run("construct_version_conflicts.sparql", ds)


def test_version_no_conflict_when_equal():
    ds, g1, g2 = _ds()
    for g in (g1, g2):
        n = EX[f"d{id(g)}"]
        g.add((EX[f"s{id(g)}"], RDIP.softwareDependency, n))
        g.add((n, RDIP.dependencyName, Literal("torch"))); g.add((n, RDIP.dependencyVersion, Literal("2.0.0")))
    assert _run("construct_version_conflicts.sparql", ds) == set()


def test_digest_conflict_absent_in_reproduction():
    ds, g1, g2 = _ds()
    g1.add((EX.spec, RDIP.imageDigest, Literal("sha256:abc")))
    assert str(RDIP.DigestConflict) in _run("construct_digest_conflicts.sparql", ds)


def test_seed_conflict_detected():
    ds, g1, g2 = _ds()
    g1.add((EX.a1, RDIP.hasParameter, EX.s1)); g1.add((EX.s1, RDF.type, RDIP.RandomSeed)); g1.add((EX.s1, RDIP.parameterName, Literal("seed"))); g1.add((EX.s1, RDIP.parameterValue, Literal("42")))
    g2.add((EX.a2, RDIP.hasParameter, EX.s2)); g2.add((EX.s2, RDF.type, RDIP.RandomSeed)); g2.add((EX.s2, RDIP.parameterName, Literal("seed"))); g2.add((EX.s2, RDIP.parameterValue, Literal("123")))
    assert str(RDIP.SeedConflict) in _run("construct_seed_conflicts.sparql", ds)


def test_hardware_cuda_conflict_detected():
    ds, g1, g2 = _ds()
    g1.add((EX.a1, RDIP.executedIn, EX.e1)); g1.add((EX.e1, RDIP.cudaVersion, Literal("11.6")))
    g2.add((EX.a2, RDIP.executedIn, EX.e2)); g2.add((EX.e2, RDIP.cudaVersion, Literal("12.1")))
    assert str(RDIP.HardwareConflict) in _run("construct_hardware_conflicts.sparql", ds)


def test_hardware_no_conflict_when_os_equal():
    ds, g1, g2 = _ds()
    g1.add((EX.a1, RDIP.executedIn, EX.e1)); g1.add((EX.e1, RDIP.osVersion, Literal("linux")))
    g2.add((EX.a2, RDIP.executedIn, EX.e2)); g2.add((EX.e2, RDIP.osVersion, Literal("linux")))
    assert _run("construct_hardware_conflicts.sparql", ds) == set()
