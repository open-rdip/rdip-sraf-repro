"""Unit tests for build-tester branch logic (early returns; no network)."""
from build_harness.build_tester import run_build_test


def test_no_installable_artifact_returns_none(tmp_path):
    artifacts = {"by_type": {}, "primary_dir": str(tmp_path)}
    r = run_build_test(str(tmp_path), artifacts, str(tmp_path))
    assert r["attempted"] is False
    assert r["method"] == "none"
    assert r["build_success"] is False


def test_setup_cfg_only_is_not_installable(tmp_path):
    # setup.cfg without setup.py / pyproject must NOT be treated as buildable
    (tmp_path / "setup.cfg").write_text("[metadata]\nname = x\n")
    artifacts = {"by_type": {"setup": "setup.cfg"}, "primary_dir": str(tmp_path)}
    r = run_build_test(str(tmp_path), artifacts, str(tmp_path))
    assert r["attempted"] is False
    assert r["method"] == "none"


def test_conda_only_build_deferred(tmp_path):
    (tmp_path / "environment.yml").write_text("dependencies:\n  - python=3.10\n")
    artifacts = {"by_type": {"conda": "environment.yml"}, "primary_dir": str(tmp_path)}
    r = run_build_test(str(tmp_path), artifacts, str(tmp_path))
    assert r["attempted"] is False  # no pip/setup target
