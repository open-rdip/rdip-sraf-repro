"""Unit tests for the recursive, priority-ranked artifact finder."""
from build_harness.artifact_finder import find_artifacts


def _mk(tmp_path, files):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return str(tmp_path)


def test_root_requirements_is_root_depth(tmp_path):
    repo = _mk(tmp_path, {"requirements.txt": "numpy\n"})
    a = find_artifacts(repo)
    assert a["by_type"]["pip"] == "requirements.txt"
    assert a["depth_note"] == "root"


def test_canonical_requirements_beats_variant(tmp_path):
    # requirements-1bit-mpi.txt would sort first alphabetically; canonical must win
    repo = _mk(tmp_path, {
        "requirements/requirements.txt": "torch\n",
        "requirements/requirements-1bit-mpi.txt": "mpi4py\n",
        "requirements/requirements-dev.txt": "pytest\n",
    })
    a = find_artifacts(repo)
    assert a["by_type"]["pip"] == "requirements/requirements.txt"


def test_dockerfile_in_subdir_is_found(tmp_path):
    repo = _mk(tmp_path, {"docker/gpu/Dockerfile": "FROM python:3.10\n"})
    a = find_artifacts(repo)
    assert a["by_type"]["docker"] == "docker/gpu/Dockerfile"
    assert a["depth_note"] == "deep"  # depth 2


def test_aux_dockerfile_loses_tie(tmp_path):
    repo = _mk(tmp_path, {
        "docker/docs/Dockerfile": "FROM python:3.10\n",
        "docker/runtime/Dockerfile": "FROM python:3.10\n",
    })
    a = find_artifacts(repo)
    # 'docs' is de-prioritised, so the runtime one wins the same-depth tie
    assert a["by_type"]["docker"] == "docker/runtime/Dockerfile"


def test_no_env_files(tmp_path):
    repo = _mk(tmp_path, {"README.md": "# hi\n", "src/main.py": "print(1)\n"})
    a = find_artifacts(repo)
    assert a["by_type"] == {}
    assert a["depth_note"] == "none"
    assert a["primary_dir"] == repo


def test_skips_vendored_dirs(tmp_path):
    repo = _mk(tmp_path, {
        "requirements.txt": "numpy\n",
        ".git/requirements.txt": "junk\n",
        "node_modules/pkg/requirements.txt": "junk\n",
    })
    a = find_artifacts(repo)
    # only the real root one is recorded
    pips = [x for x in a["all"] if x["type"] == "pip"]
    assert len(pips) == 1 and pips[0]["rel_path"] == "requirements.txt"


def test_primary_dir_prefers_docker_over_pip(tmp_path):
    repo = _mk(tmp_path, {
        "requirements.txt": "numpy\n",
        "Dockerfile": "FROM python:3.10\n",
    })
    a = find_artifacts(repo)
    assert a["primary_dir"] == repo  # both at root; docker anchors primary
