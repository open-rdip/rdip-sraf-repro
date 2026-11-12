"""Safety tests for analysis/pool_extractors.py.

This script appends to graphs that cannot be un-appended: `map_extraction`
mints random UUIDs, so pooled triples are not subtractable, and the canonical
graphs exist nowhere else. Every guard that stands between a mistake and
re-cloning 95 repositories is tested here.
"""
import json
import os
import sys
import types
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def pool(monkeypatch):
    """Import the module with the triplestore stubbed out."""
    calls = {"append": [], "delete": [], "upload": []}
    stub = types.ModuleType("triplestore_client")
    stub.append_graph = lambda uri, ttl: calls["append"].append(uri)
    stub.delete_graph = lambda uri: calls["delete"].append(uri)
    stub.upload_graph = lambda uri, ttl: calls["upload"].append(uri)
    stub.count_triples = lambda uri: 123
    stub.graph_exists = lambda uri: True
    stub.fetch_graph = lambda uri: []
    monkeypatch.setitem(sys.modules, "triplestore_client", stub)
    sys.path.insert(0, ROOT)
    for m in list(sys.modules):
        if m.startswith("analysis.pool_extractors"):
            del sys.modules[m]
    import analysis.pool_extractors as p
    p._calls = calls
    return p


def test_a_directory_without_a_manifest_is_not_a_snapshot(pool, tmp_path):
    """The guard that stops `pool --snapshot /some/empty/dir` wiping the
    baseline. Without this, a typo in the path reads as 'backed up'."""
    with pytest.raises(SystemExit) as e:
        pool._check_snapshot(str(tmp_path))
    assert "MANIFEST" in str(e.value)


def test_a_manifest_missing_its_turtle_files_is_rejected(pool, tmp_path):
    """A half-written snapshot is more dangerous than none, because it looks
    like protection."""
    json.dump({"created": "x", "graphs": {"study001": {"triples": 5}}},
              open(tmp_path / "MANIFEST.json", "w"))
    with pytest.raises(SystemExit) as e:
        pool._check_snapshot(str(tmp_path))
    assert "incomplete" in str(e.value)


def test_a_complete_snapshot_is_accepted(pool, tmp_path):
    json.dump({"created": "x", "graphs": {"study001": {"triples": 5}}},
              open(tmp_path / "MANIFEST.json", "w"))
    (tmp_path / "study001.ttl").write_text("# turtle")
    assert pool._check_snapshot(str(tmp_path))["graphs"]["study001"]["triples"] == 5


def test_an_existing_marker_prevents_merging_the_same_model_twice(pool, tmp_path, monkeypatch):
    """Pooling is append-only, so a double merge doubles a model's triples and
    is not undoable. Markers are per (study, model), unlike merge_winner's
    model-agnostic ones, which would otherwise report study001 as done after
    Mistral and silently skip every later model."""
    monkeypatch.setattr(pool, "MARK_DIR", str(tmp_path))
    (tmp_path / "study001__grok-4-7.pooled").write_text("{}")
    status, n = pool._merge_one("study001", "grok-4-7", dry_run=False)
    assert status == "skip" and n == 0
    assert pool._calls["append"] == []


def test_a_marker_for_one_model_does_not_block_another(pool, tmp_path, monkeypatch):
    monkeypatch.setattr(pool, "MARK_DIR", str(tmp_path))
    (tmp_path / "study001__grok-4-7.pooled").write_text("{}")
    monkeypatch.setattr(pool, "EXTRACTIONS", str(tmp_path))
    assert pool._merge_one("study001", "gpt-5", dry_run=False)[0] == "no-extraction"


def test_a_missing_extraction_is_reported_not_silently_skipped(pool, tmp_path, monkeypatch):
    monkeypatch.setattr(pool, "MARK_DIR", str(tmp_path))
    monkeypatch.setattr(pool, "EXTRACTIONS", str(tmp_path))
    assert pool._merge_one("study999", "grok-4-7", dry_run=False)[0] == "no-extraction"
    assert pool._calls["append"] == []


def test_dry_run_never_writes(pool, tmp_path, monkeypatch):
    monkeypatch.setattr(pool, "MARK_DIR", str(tmp_path))
    monkeypatch.setattr(pool, "EXTRACTIONS", str(tmp_path))
    json.dump({"study_id": "study001", "metadata": {"datasets": [{"name": "CIFAR-10"}]}},
              open(tmp_path / "study001__grok-4-7.json", "w"))
    status, n = pool._merge_one("study001", "grok-4-7", dry_run=True)
    assert status == "would-merge"
    assert pool._calls["append"] == []
    assert not list(tmp_path.glob("*.pooled"))


def test_the_pool_excludes_the_contaminated_and_partial_models(pool):
    """Gemini generated the ground truth; Opus covers 12 of 95 studies and
    would confound the gold tier with deeper extraction."""
    assert "gemini-3-8-flash" not in pool.DEFAULT_POOL
    assert "claude-opus-5-5" not in pool.DEFAULT_POOL
    assert set(pool.DEFAULT_POOL) == {"grok-4-7", "gpt-5", "claude-sonnet-5-5"}
    assert pool.ALREADY_MERGED == [
        "redhatai-mistral-small-24b-instruct-2501-quantized-w8a8"]


# ── the bug that shipped: an empty snapshot read as success ─────────────────

def test_an_empty_snapshot_is_refused(pool, tmp_path):
    """Shipped broken on 12 Nov. `snapshot` found 0 graphs, printed
    'snapshot complete: 0 graphs' and invited the user to pool. Pooling into
    graphs that do not exist CREATES them holding only the pooled models,
    which destroys the Mistral baseline the snapshot exists to protect."""
    json.dump({"created": "x", "graphs": {}}, open(tmp_path / "MANIFEST.json", "w"))
    with pytest.raises(SystemExit) as e:
        pool._check_snapshot(str(tmp_path))
    assert "0 graphs" in str(e.value)


def test_a_partial_snapshot_is_refused(pool, tmp_path):
    json.dump({"created": "x", "partial": True, "expected": 95,
               "graphs": {"study001": {"triples": 5}}},
              open(tmp_path / "MANIFEST.json", "w"))
    (tmp_path / "study001.ttl").write_text("# turtle")
    with pytest.raises(SystemExit) as e:
        pool._check_snapshot(str(tmp_path))
    assert "PARTIAL" in str(e.value)


def test_fewer_graphs_than_expected_is_refused(pool, tmp_path):
    json.dump({"created": "x", "expected": 95,
               "graphs": {"study001": {"triples": 5}}},
              open(tmp_path / "MANIFEST.json", "w"))
    (tmp_path / "study001.ttl").write_text("# turtle")
    with pytest.raises(SystemExit) as e:
        pool._check_snapshot(str(tmp_path))
    assert "expected 95" in str(e.value)


def test_verify_refuses_to_rerun_on_an_already_pooled_study(pool, tmp_path, monkeypatch):
    """Shipped broken 12 Nov. `verify` captures 'before' from the live store,
    so a second call captured the pooled graph and 'restored' study001 to 759
    triples instead of 251, reporting success. Only the snapshot saved it."""
    monkeypatch.setattr(pool, "MARK_DIR", str(tmp_path))
    (tmp_path / "study001__grok-4-7.pooled").write_text("{}")
    args = types.SimpleNamespace(study="study001", models=None, restore=True)
    with pytest.raises(SystemExit) as e:
        pool.cmd_verify(args)
    assert "already pooled" in str(e.value)
    assert "restore --snapshot" in str(e.value)
