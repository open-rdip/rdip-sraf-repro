# lifter/lifter.py
"""
Main entry point for Phase I — the Metadata Lifter.

Usage:
  python lifter/lifter.py --study-id study001 --repo-dir /path/to/repo
  python lifter/lifter.py --study-id study001 --docker-image pytorch/pytorch:2.1.0-cuda12.1

Loads the RDIP ontology, parses available env files,
maps to RDIP triples, and uploads to Oxigraph.
"""

import sys
import os
import argparse
from parsers.dmp_parser import parse_madmp
from mapper.rdip_mapper import map_dmp

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ontology_loader import ensure_latest
from triplestore_client import upload_graph, count_triples, graph_exists

from lifter.parsers.docker_parser import (
    from_repo as docker_from_repo,
    parse_dockerfile,
    inspect_image,
    parse_docker_inspect,
)
from lifter.parsers.conda_parser  import from_repo as conda_from_repo
from lifter.parsers.pip_parser    import from_repo as pip_from_repo

from lifter.mapper.rdip_mapper import (
    map_docker, map_conda, map_pip,
    merge_graphs, to_turtle,
)

GRAPH_BASE = "https://w3id.org/rdip/graph"

def graph_uri(study_id: str) -> str:
    return f"{GRAPH_BASE}/{study_id}"

def lift_from_repo(study_id: str, repo_dir: str,
                   overwrite: bool = False) -> dict:
    """
    Auto-detect and lift all available environment files from a repo directory.
    Returns a summary dict.
    """
    uri = graph_uri(study_id)
    print(f"\n[Lifter] Study: {study_id}")
    print(f"[Lifter] Repo:  {repo_dir}")
    print(f"[Lifter] Graph: {uri}")

    if graph_exists(uri) and not overwrite:
        print(f"[Lifter] Graph already exists — skipping. "
              f"Use --overwrite to force.")
        return {"study_id": study_id, "status": "skipped", "triples": 0}

    graphs   = []
    summary  = {
        "study_id":    study_id,
        "docker":      False,
        "conda":       False,
        "pip":         False,
        "triples":     0,
        "status":      "ok",
    }

    # Docker
    docker_parsed = docker_from_repo(repo_dir)
    if docker_parsed:
        g = map_docker(study_id, docker_parsed)
        graphs.append(g)
        summary["docker"] = True
        print(f"[Lifter] Docker: {len(g)} triples")

    # Conda
    conda_parsed = conda_from_repo(repo_dir)
    if conda_parsed:
        g = map_conda(study_id, conda_parsed)
        graphs.append(g)
        summary["conda"] = True
        print(f"[Lifter] Conda:  {len(g)} triples")

    # Pip
    pip_parsed = pip_from_repo(repo_dir)
    if pip_parsed:
        g = map_pip(study_id, pip_parsed)
        graphs.append(g)
        summary["pip"] = True
        print(f"[Lifter] Pip:    {len(g)} triples")

    if not graphs:
        print(f"[Lifter] WARNING: No environment files found in {repo_dir}")
        summary["status"] = "no_env_files"
        return summary

    # Merge and upload
    merged = merge_graphs(*graphs)
    turtle = to_turtle(merged)
    upload_graph(uri, turtle)

    summary["triples"] = count_triples(uri)
    print(f"[Lifter] Uploaded {summary['triples']} triples to <{uri}>")
    return summary

def lift_from_docker_image(study_id: str, image_ref: str,
                            overwrite: bool = False) -> dict:
    """Lift directly from a Docker image reference."""
    uri = graph_uri(study_id)
    print(f"\n[Lifter] Study: {study_id}")
    print(f"[Lifter] Image: {image_ref}")

    if graph_exists(uri) and not overwrite:
        print(f"[Lifter] Graph already exists — skipping.")
        return {"study_id": study_id, "status": "skipped"}

    inspect  = inspect_image(image_ref)
    parsed   = parse_docker_inspect(inspect)
    g        = map_docker(study_id, parsed)
    turtle   = to_turtle(g)
    upload_graph(uri, turtle)

    n = count_triples(uri)
    print(f"[Lifter] Uploaded {n} triples to <{uri}>")
    return {"study_id": study_id, "status": "ok", "triples": n}

def lift_dmp(study_id: str, dmp_file: str) -> str:
    """Ingest an maDMP JSON file into the RDIP Knowledge Graph."""
    print(f"[Lifter] Parsing maDMP: {dmp_file}")
    parsed = parse_madmp(dmp_file)
    g = map_dmp(study_id, parsed)
    turtle = to_turtle(g)
    graph_uri = f"https://w3id.org/rdip/graph/{study_id}"
    upload_graph(graph_uri, turtle)
    print(f"[Lifter] DMP: uploaded {len(g)} triples to <{graph_uri}>")
    return turtle


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RDIP Metadata Lifter — Phase I"
    )
    parser.add_argument("--study-id",     required=True,
                        help="Unique identifier for this study")
    parser.add_argument("--repo-dir",     default=None,
                        help="Path to a cloned repository")
    parser.add_argument("--docker-image", default=None,
                        help="Docker image reference (e.g. pytorch/pytorch:2.1.0)")
    parser.add_argument("--overwrite",    action="store_true",
                        help="Overwrite existing graph if it exists")
    parser.add_argument("--skip-ontology-check", action="store_true",
                        help="Skip ontology version check (faster for bulk runs)")
    parser.add_argument("--dmp-file", default=None,
                    help="Path to maDMP JSON (RDA DMP Common Standard)")
    args = parser.parse_args()

    # Ensure ontology is loaded
    if not args.skip_ontology_check:
        meta = ensure_latest()
        print(f"[Lifter] Ontology version: {meta.get('version_info')}")

    if args.repo_dir:
        result = lift_from_repo(
            args.study_id, args.repo_dir, args.overwrite
        )
    elif args.docker_image:
        result = lift_from_docker_image(
            args.study_id, args.docker_image, args.overwrite
        )
    else:
        parser.error("Provide either --repo-dir or --docker-image")

    print(f"\n[Lifter] Result: {result}")


if __name__ == "__main__":
    main()
