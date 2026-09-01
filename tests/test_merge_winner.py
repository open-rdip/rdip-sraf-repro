"""Tests for merging the winning model's extractions into canonical graphs."""
import json
import sys
import types

# Stub triplestore before importing (no Oxigraph in CI).
_ts = types.ModuleType("triplestore_client")
_appended = []
_ts.append_graph = lambda uri, turtle: _appended.append((uri, turtle))
_ts.count_triples = lambda uri: 0
sys.modules["triplestore_client"] = _ts

import rag_pipeline.merge_winner as mw  # noqa: E402


def test_study_of_filename():
    assert mw._study_of("/x/study007__qwen-14b.json", "qwen-14b") == "study007"
    assert mw._study_of("/x/study007__m.json", "m") == "study007"


def test_merge_targets_canonical_graph(tmp_path, monkeypatch):
    ext = tmp_path / "ext"; ext.mkdir()
    marks = tmp_path / "marks"
    (ext / "study003__win.json").write_text(json.dumps({
        "study_id": "study003",
        "metadata": {"datasets": [{"name": "GLUE"}], "methods": [],
                     "dependencies": [], "hyperparameters": [], "random_seeds": [],
                     "hardware": {}, "evaluation_results": []}}))

    captured = {}

    def fake_map(sid, merged):
        captured["sid"] = sid
        return ["t1", "t2"]
    monkeypatch.setattr(mw, "map_extraction", fake_map)
    monkeypatch.setattr(mw, "to_turtle", lambda g: "<ttl>")
    monkeypatch.setattr(mw, "append_graph",
                        lambda uri, ttl: captured.__setitem__("uri", uri))
    monkeypatch.setattr(mw, "count_triples", lambda uri: 42)

    res = mw.merge("win", str(ext), str(marks))
    assert captured["sid"] == "study003"
    assert captured["uri"] == "https://w3id.org/rdip/graph/study003"   # canonical, not /ext/
    assert res == [("study003", "merged", 2)]
    assert (marks / "study003.merged").exists()       # marker written


def test_merge_is_resumable(tmp_path, monkeypatch):
    ext = tmp_path / "ext"; ext.mkdir()
    marks = tmp_path / "marks"; marks.mkdir()
    (ext / "study001__win.json").write_text(json.dumps({"metadata": {}}))
    (marks / "study001.merged").write_text("{}")      # already done

    monkeypatch.setattr(mw, "map_extraction", lambda sid, merged: ["t"])
    monkeypatch.setattr(mw, "to_turtle", lambda g: "x")
    monkeypatch.setattr(mw, "append_graph", lambda uri, ttl: None)
    monkeypatch.setattr(mw, "count_triples", lambda uri: 0)

    res = mw.merge("win", str(ext), str(marks))
    assert res == [("study001", "skip", 0)]           # skipped via marker
