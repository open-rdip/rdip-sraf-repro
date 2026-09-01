"""Merge per-task graph exports into the durable triplestore.

Each array task wrote ~/triplestore/exports/<study_id>.ttl (plain turtle, no
graph context). This loads each into its named graph in a SINGLE Oxigraph
instance — the single-writer step that avoids the NFS-locking the handoff
warned about. Run it once after the corpus array finishes.

Usage (on the login node, against a durable Oxigraph you start first):
  ~/bin/oxigraph serve --location ~/triplestore --bind 127.0.0.1:7878 &
  cd ~/rdip-sre
  OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT=7878 \
      ~/envs/sraf/bin/python -m build_harness.merge_results
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from triplestore_client import upload_graph, count_triples  # noqa: E402


def graph_uri(study_id: str) -> str:
    return f"https://w3id.org/rdip/graph/{study_id}"


def main():
    export_dir = Path(os.getenv(
        "SRAF_EXPORT_DIR", str(REPO_ROOT.parent / "triplestore" / "exports")))
    ttls = sorted(export_dir.glob("*.ttl"))
    if not ttls:
        print(f"No .ttl exports in {export_dir}")
        return

    total = 0
    for ttl in ttls:
        study_id = ttl.stem
        turtle = ttl.read_text(encoding="utf-8")
        uri = graph_uri(study_id)
        upload_graph(uri, turtle)
        n = count_triples(uri)
        total += n
        print(f"  {study_id:14s} -> <{uri}>  ({n} triples)")

    print(f"\nMerged {len(ttls)} graphs, {total} triples total into the durable store.")


if __name__ == "__main__":
    main()
