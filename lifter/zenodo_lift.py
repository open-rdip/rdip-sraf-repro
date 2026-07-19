"""Lift Zenodo/DataCite registry metadata into an artifact's RDIP study graph.

The FAIR-R scorer only sees what is in the graph. `process_repo` populates the
graph from the GitHub clone, which does NOT contain the registry-level features
that make an archived artifact exemplary: the persistent identifier (DOI), the
Zenodo landing page, the declared access level and data licence, the DataCite
related-identifier links (article <-> code <-> data), and the community
file-format standard. Those live on the Zenodo record. This module fetches that
record and emits the corresponding RDIP triples so those criteria can be scored.

This is a general capability: it should be run for any artifact that actually
has a DOI. Ordinary GitHub repositories without a DOI legitimately gain nothing.

Prereq: Oxigraph serving the triplestore (OXIGRAPH_HOST/PORT set).

Usage:
  ~/envs/sraf/bin/python -m lifter.zenodo_lift --study-id study040 \
      --doi 10.5281/zenodo.16374814
  # or --record-id 16374814 ; add --dry-run to print Turtle without uploading
Then re-score:  ~/envs/sraf/bin/python scripts/dump_fair_r.py study040
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import requests                                                    # noqa: E402
from rdflib import Graph, Literal, RDF, XSD, URIRef                # noqa: E402
from lifter.mapper.rdip_mapper import (                           # noqa: E402
    RDIP, DCAT, _base_graph, study_uri, BASE)
from triplestore_client import append_graph, count_triples        # noqa: E402

GRAPH_BASE = "https://w3id.org/rdip/graph"

# A few common Zenodo licence ids -> SPDX identifiers.
SPDX = {
    "cc-by-4.0": "CC-BY-4.0", "cc-by-sa-4.0": "CC-BY-SA-4.0",
    "cc-zero": "CC0-1.0", "cc0-1.0": "CC0-1.0", "mit": "MIT",
    "apache-2.0": "Apache-2.0", "bsd-3-clause": "BSD-3-Clause",
    "gpl-3.0": "GPL-3.0", "gpl-3.0-only": "GPL-3.0-only",
    "gpl-3.0-or-later": "GPL-3.0-or-later",
}


def dataset_uri(study_id: str) -> URIRef:
    return URIRef(f"{BASE}dataset-{study_id}-zenodo")


def _record_id_from_doi(doi: str) -> str:
    m = re.search(r"zenodo\.(\d+)", doi)
    return m.group(1) if m else doi.strip()


def fetch_zenodo(record_id: str) -> dict:
    url = f"https://zenodo.org/api/records/{record_id}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def map_zenodo(study_id: str, z: dict) -> Graph:
    """Build RDIP triples from a Zenodo record JSON."""
    g = _base_graph()
    activity = study_uri(study_id)
    dataset = dataset_uri(study_id)
    md = z.get("metadata", {}) or {}

    g.add((activity, RDF.type, RDIP.ResearchActivity))
    g.add((dataset, RDF.type, DCAT.Dataset))
    g.add((activity, RDIP.usedDataset, dataset))

    # Persistent identifier (Findable, -> full): a resolvable DOI.
    doi = z.get("doi") or md.get("doi")
    if doi:
        doi_url = str(doi) if str(doi).startswith("http") else f"https://doi.org/{doi}"
        g.add((activity, RDIP.identifier, Literal(doi_url, datatype=XSD.anyURI)))

    # Landing page (Findable).
    links = z.get("links", {}) or {}
    landing = (links.get("self_html") or links.get("html")
               or f"https://zenodo.org/records/{z.get('id', '')}")
    g.add((dataset, RDIP.datasetLandingPage, Literal(landing, datatype=XSD.anyURI)))

    # Data licence (Accessible).
    lic = md.get("license")
    lic_id = lic.get("id") if isinstance(lic, dict) else lic
    if lic_id:
        g.add((dataset, RDIP.dataLicense,
               Literal(SPDX.get(str(lic_id).lower(), lic_id), datatype=XSD.string)))

    # Access level (Accessible, -> full): controlled vocabulary.
    access = md.get("access_right") or (z.get("access", {}) or {}).get("record")
    if access:
        val = "open" if "open" in str(access).lower() or "public" in str(access).lower() \
              else str(access).lower()
        g.add((dataset, RDIP.accessLevel, Literal(val, datatype=XSD.string)))

    # Related links (Interoperable): DataCite article <-> code <-> data.
    for rel in md.get("related_identifiers", []) or []:
        ident = rel.get("identifier")
        rtype = (rel.get("relation") or "").lower()
        if not ident:
            continue
        url = str(ident) if str(ident).startswith("http") else f"https://doi.org/{ident}"
        if any(k in rtype for k in ("supplementto", "documents", "ispartof", "publication")):
            g.add((activity, RDIP.generatesPublication, Literal(url, datatype=XSD.anyURI)))
        else:
            g.add((activity, RDIP.citesDataset, Literal(url, datatype=XSD.anyURI)))

    # Community file-format standard (Reusable).
    fmts = set()
    for f in z.get("files", []) or []:
        key = f.get("key") or ""
        if "." in key:
            fmts.add(key.rsplit(".", 1)[-1].lower())
    for fmt in sorted(fmts)[:4]:
        g.add((dataset, RDIP.dataFormat, Literal(fmt, datatype=XSD.string)))
    if not fmts:
        g.add((dataset, RDIP.dataFormat, Literal("datacite", datatype=XSD.string)))

    return g


def main():
    ap = argparse.ArgumentParser(description="Lift Zenodo/DataCite metadata into a study graph")
    ap.add_argument("--study-id", required=True)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--doi", help="e.g. 10.5281/zenodo.16374814")
    grp.add_argument("--record-id", help="Zenodo numeric record id")
    ap.add_argument("--json", help="load a saved Zenodo API JSON instead of fetching")
    ap.add_argument("--dry-run", action="store_true", help="print Turtle, do not upload")
    a = ap.parse_args()

    if a.json:
        z = json.load(open(a.json))
    else:
        rid = a.record_id or _record_id_from_doi(a.doi)
        z = fetch_zenodo(rid)

    graph = map_zenodo(a.study_id, z)
    print(graph.serialize(format="turtle"))
    print(f"# {len(graph)} triples for {a.study_id}")
    if a.dry_run:
        return
    guri = f"{GRAPH_BASE}/{a.study_id}"
    append_graph(guri, graph.serialize(format="turtle"))
    print(f"[Oxigraph] appended {len(graph)} triples to <{guri}> — now {count_triples(guri)} total")


if __name__ == "__main__":
    main()
