"""Unit tests for repo-level metadata extraction (license, commit, identifier)."""
import subprocess

from build_harness.repo_metadata import _detect_license, extract_repo_metadata


MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person"
APACHE = "Apache License\nVersion 2.0, January 2004\nhttp://www.apache.org/licenses/"
BSD3 = ("Redistribution and use in source and binary forms ...\n"
        "Neither the name of the copyright holder nor the names")


def test_detect_mit(tmp_path):
    (tmp_path / "LICENSE").write_text(MIT)
    assert _detect_license(str(tmp_path)) == "MIT"


def test_detect_apache(tmp_path):
    (tmp_path / "LICENSE.txt").write_text(APACHE)
    assert _detect_license(str(tmp_path)) == "Apache-2.0"


def test_detect_bsd3_over_bsd2(tmp_path):
    (tmp_path / "LICENSE").write_text(BSD3)
    assert _detect_license(str(tmp_path)) == "BSD-3-Clause"


def test_unrecognised_license_is_custom(tmp_path):
    (tmp_path / "COPYING").write_text("Some bespoke license text with no signature.")
    assert _detect_license(str(tmp_path)) == "LicenseRef-Custom"


def test_no_license_returns_none(tmp_path):
    assert _detect_license(str(tmp_path)) is None


def test_extract_metadata_with_git(tmp_path):
    # init a real git repo so commit-hash extraction is exercised
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    run = lambda *a: subprocess.run(a, cwd=tmp_path, env={**env, "PATH": __import__("os").environ["PATH"]}, check=True, capture_output=True)
    run("git", "init", "-q")
    (tmp_path / "LICENSE").write_text(MIT)
    run("git", "add", "-A")
    run("git", "commit", "-qm", "init")

    meta = extract_repo_metadata(str(tmp_path), "https://github.com/x/y")
    assert meta["identifier"] == "https://github.com/x/y"
    assert meta["software_license"] == "MIT"
    assert meta["commit_hash"] and len(meta["commit_hash"]) == 40


def test_identifier_override(tmp_path):
    meta = extract_repo_metadata(str(tmp_path), "https://github.com/x/y",
                                 identifier="arXiv:2303.08302")
    assert meta["identifier"] == "arXiv:2303.08302"
    assert meta["commit_hash"] is None  # not a git repo
