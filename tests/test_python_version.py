"""Unit tests for declared-Python resolution and interpreter selection."""
import pytest

from build_harness.python_version import (
    _tup, _from_specifier, _norm, resolve_python_version, choose_interpreter,
)


def test_tuple_ordering_not_float():
    # the bug we fixed: as floats, 3.9 > 3.12 and "3.10" -> 3.1
    assert _tup("3.10") > _tup("3.9")
    assert _tup("3.12") > _tup("3.11") > _tup("3.9")


@pytest.mark.parametrize("spec,expected", [
    (">=3.10,<3.11", "3.10"),
    (">=3.8", "3.12"),
    (">=3.7,<3.10", "3.9"),
    ("<3.11,>=3.10", "3.10"),
    ("==3.8", "3.8"),
    (">=3.13", None),
])
def test_from_specifier(spec, expected):
    assert _from_specifier(spec) == expected


@pytest.mark.parametrize("v,expected", [
    ("3.7", "3.8"), ("3.6", "3.8"), ("3.10", "3.10"),
    ("3.11", "3.11"), ("3.13", "3.12"), ("3.9", "3.9"),
])
def test_norm(v, expected):
    assert _norm(v) == expected


def test_resolve_from_conda(tmp_path):
    (tmp_path / "environment.yml").write_text("dependencies:\n  - python=3.9\n")
    ver, src = resolve_python_version(str(tmp_path), {"by_type": {"conda": "environment.yml"}})
    assert (ver, src) == ("3.9", "conda")


def test_resolve_from_dockerfile(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.8-slim\n")
    ver, src = resolve_python_version(str(tmp_path), {"by_type": {"docker": "Dockerfile"}})
    assert ver == "3.8" and src == "dockerfile"


def test_resolve_from_python_requires(tmp_path):
    (tmp_path / "setup.py").write_text("setup(python_requires='>=3.10,<3.11')\n")
    ver, src = resolve_python_version(str(tmp_path), {"by_type": {"setup": "setup.py"}})
    assert ver == "3.10" and src == "python_requires"


def test_resolve_undeclared(tmp_path):
    ver, src = resolve_python_version(str(tmp_path), {"by_type": {}})
    assert ver is None and src == "default"


def test_choose_interpreter_falls_back_when_no_ladder(monkeypatch):
    # point the ladder at an empty dir -> graceful fallback to current interpreter
    monkeypatch.setenv("SRAF_PY_LADDER", "/nonexistent/ladder")
    import importlib, build_harness.python_version as pv
    importlib.reload(pv)
    path, used, available = pv.choose_interpreter("3.9")
    assert available is False and path  # falls back, still returns a path
    importlib.reload(pv)  # restore default
