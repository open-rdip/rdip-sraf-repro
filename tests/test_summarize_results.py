"""Unit tests for the results aggregator's row extraction + summary."""
import json

from analysis import summarize_results as sr


def _write(tmp_path, recs):
    for r in recs:
        (tmp_path / f"{r['study_id']}.json").write_text(json.dumps(r))


SAMPLES = [
    {"study_id": "study001", "status": "ok",
     "artifacts": {"by_type": {"docker": "Dockerfile", "pip": "requirements.txt"}, "depth_note": "root", "n_found": 5},
     "lift": {"triples": 148},
     "build": {"resolve_success": True, "build_success": True, "stage_failed": None},
     "fair_r": {"total_score": 27.5, "tier": "poor"},
     "repo_meta": {"software_license": "MIT", "commit_hash": "abc"},
     "python": {"declared": "3.9", "used": "3.9", "ladder_available": True}},
    {"study_id": "study002", "status": "ok",
     "artifacts": {"by_type": {"pip": "requirements.txt"}, "depth_note": "root", "n_found": 1},
     "lift": {"triples": 30},
     "build": {"resolve_success": True, "build_success": False, "stage_failed": "build-install"},
     "fair_r": {"total_score": 17.5, "tier": "poor"},
     "repo_meta": {"software_license": None, "commit_hash": "def"},
     "python": {"declared": None, "used": "3.10", "ladder_available": True}},
    {"study_id": "study003", "status": "ok",
     "artifacts": {"by_type": {}, "depth_note": "none", "n_found": 0},
     "lift": {"triples": 5},
     "build": {"resolve_success": None, "build_success": False, "stage_failed": None},
     "fair_r": {"total_score": 17.5, "tier": "poor"},
     "repo_meta": {"software_license": None, "commit_hash": "ghi"},
     "python": {"declared": None, "used": "3.10", "ladder_available": True}},
]


def test_row_extraction():
    row = sr._row(SAMPLES[0])
    assert row["has_docker"] and row["has_pip"]
    assert row["resolve_success"] is True and row["build_success"] is True
    assert row["py_used"] == "3.9" and row["ladder_ok"] is True


def test_summary_counts(tmp_path, monkeypatch):
    _write(tmp_path, SAMPLES)
    monkeypatch.setattr(sr, "RESULTS_DIR", tmp_path)
    rows = [sr._row(r) for r in SAMPLES]
    text = "\n".join(sr.summarize(rows))
    # 2 of 3 had a build attempted; 1 of 2 built
    assert "Build attempted: 2/3" in text
    assert "build succeeds:      1/2" in text
    # 1 of 3 has no env files
    assert "repos with NO env files: 1/3" in text
    # interpreter section present
    assert "Build interpreter" in text
