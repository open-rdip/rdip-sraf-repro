"""Guard: the A/B manifest must not fabricate a record of a run that did not
happen. Third instance of the same class of bug in two days, after the empty
snapshot and the no-op restore, so it is pinned.
"""
import os, sys, types, json, pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_manifest_refuses_absent_inputs(tmp_path, monkeypatch):
    """Shipped broken 12 Nov: ran before the A/B existed, wrote a RUN.json
    recording nothing, then crashed formatting a None mean."""
    sys.path.insert(0, ROOT)
    stub = types.ModuleType("triplestore_client")
    for n in ("append_graph","delete_graph","upload_graph","count_triples",
              "graph_exists","fetch_graph"):
        setattr(stub, n, lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "triplestore_client", stub)
    for m in [m for m in sys.modules if m.startswith("analysis.ab_manifest")]:
        del sys.modules[m]
    import analysis.ab_manifest as m
    monkeypatch.setattr(m, "AB", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["x", "--snapshot", "backups/none"])
    with pytest.raises(SystemExit) as e:
        m.main()
    msg = str(e.value)
    assert "no A/B outputs" in msg and "ab_pool_compare" in msg
    assert not list(tmp_path.glob("RUN.json")), "must not write a record of nothing"
