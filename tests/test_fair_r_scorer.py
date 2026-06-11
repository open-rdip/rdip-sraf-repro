"""Unit tests for the graded, priority-weighted FAIR-R scorer.

The triplestore layer is stubbed, so these test the scoring ARITHMETIC
(priority -> weight, level -> points, aggregation, tier) without Oxigraph.
"""
import sys
import types

# Stub the triplestore client before importing the scorer (no Oxigraph needed).
_stub = types.ModuleType("triplestore_client")
_stub.sparql_query = lambda q: {"boolean": False}
sys.modules["triplestore_client"] = _stub

import dashboard.fair_r_scorer as fr  # noqa: E402


def test_criterion_max_by_priority():
    # Findable: essential(3) + essential(3) + important(2) = 8; PID = 3/8 * 15
    f = fr.DIMENSIONS["Findable"]
    assert abs(fr._criterion_max(f["criteria"][0], f) - 5.625) < 0.01


def test_criterion_max_by_fraction():
    # Reproducible R1 has an explicit fraction 0.4 of 30
    rep = fr.DIMENSIONS["Reproducible"]
    assert abs(fr._criterion_max(rep["criteria"][0], rep) - 12.0) < 0.01


def test_reusable_priority_split():
    # Reusable: essential(3)+important(2)+useful(1)=6; software licence = 3/6 * 20 = 10
    r = fr.DIMENSIONS["Reusable"]
    assert abs(fr._criterion_max(r["criteria"][0], r) - 10.0) < 0.01


def test_graded_points_and_levels(monkeypatch):
    levels = {
        "Persistent identifier": 1,            # partial
        "Software licence": 2,                 # full
        "Computational environment (R1)": 1,   # partial
    }
    monkeypatch.setattr(fr, "_grade", lambda g, c: levels.get(c["label"], 0))
    res = fr.compute_fair_r("study_x")

    fcrit = {c["label"]: c for c in res["dimension_scores"]["Findable"]["criteria"]}
    pid = fcrit["Persistent identifier"]
    assert pid["level"] == "partial"
    assert abs(pid["points"] - 2.81) < 0.05            # 0.5 * 5.625

    rcrit = {c["label"]: c for c in res["dimension_scores"]["Reusable"]["criteria"]}
    assert rcrit["Software licence"]["level"] == "full"
    assert abs(rcrit["Software licence"]["points"] - 10.0) < 0.05

    repro = {c["label"]: c for c in res["dimension_scores"]["Reproducible"]["criteria"]}
    assert abs(repro["Computational environment (R1)"]["points"] - 6.0) < 0.05  # 0.5 * 12

    assert 0 <= res["total_score"] <= 100
    assert res["tier"] in ("poor", "fair", "good", "excellent")


def test_recommendations_sorted_essential_first(monkeypatch):
    monkeypatch.setattr(fr, "_grade", lambda g, c: 0)   # everything absent
    res = fr.compute_fair_r("study_y")
    prios = [r["priority"] for r in res["recommendations"]]
    rank = {"essential": 0, "important": 1, "useful": 2, "—": 3}
    assert prios == sorted(prios, key=lambda p: rank[p])   # essentials first
    assert res["total_score"] == 0.0 and res["tier"] == "poor"


def test_perfect_score_is_100(monkeypatch):
    monkeypatch.setattr(fr, "_grade", lambda g, c: 2)   # everything full
    res = fr.compute_fair_r("study_z")
    assert abs(res["total_score"] - 100.0) < 0.01
    assert res["tier"] == "excellent"
