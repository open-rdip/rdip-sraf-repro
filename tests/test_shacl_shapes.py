"""Tests for the FAIR-R SHACL shapes (parse + validate behaviour)."""
import glob
from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib")
pytest.importorskip("pyshacl")
from pyshacl import validate  # noqa: E402

SHACL_DIR = Path(__file__).resolve().parent.parent / "sre_engine" / "shacl"


def _shapes():
    g = rdflib.Graph()
    for f in glob.glob(str(SHACL_DIR / "*.ttl")):
        g.parse(f, format="turtle")
    return g


def _data(ttl):
    g = rdflib.Graph()
    g.parse(data="@prefix rdip: <https://w3id.org/rdip/> .\n" + ttl, format="turtle")
    return g


def test_all_shapes_parse():
    assert len(_shapes()) > 100


def test_incomplete_activity_fails_essential_criteria():
    data = _data('<http://ex/a> a rdip:ResearchActivity ; '
                 'rdip:identifier "https://github.com/x/y" . '
                 '<http://ex/s> a rdip:SoftwareApplication ; rdip:commitHash "abc" .')
    conforms, _, txt = validate(data, shacl_graph=_shapes(),
                                inference="rdfs", allow_warnings=True)
    assert conforms is False                 # essential criteria violated
    assert "softwareLicense" in txt          # missing licence flagged
    assert "rdfs:label" in txt or "label" in txt  # missing descriptive metadata


def test_licensed_software_not_flagged():
    data = _data('<http://ex/s> a rdip:SoftwareApplication ; '
                 'rdip:softwareLicense "MIT" ; rdip:commitHash "abc" .')
    _, _, txt = validate(data, shacl_graph=_shapes(),
                         inference="rdfs", allow_warnings=True)
    assert "softwareLicense" not in txt      # licence present -> no violation
