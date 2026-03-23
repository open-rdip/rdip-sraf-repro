# sre_engine/diff_engine.py
"""
Semantic Diff Engine — Phase III core.

Implements the three-stage algorithm:
  Stage 1: Graph alignment (match nodes by name across named graphs)
  Stage 2: Conflict materialisation via SPARQL CONSTRUCT queries
  Stage 3: SHACL presence validation

All conflict triples are written to a dedicated conflict named graph
and returned as a ConflictReport.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rdflib import Graph, Namespace, URIRef
from pyshacl import validate

from triplestore_client import (
    sparql_construct,
    fetch_graph,
    upload_graph,
    count_triples,
    graph_exists,
)

RDIP       = Namespace("https://w3id.org/rdip/")
GRAPH_BASE = "https://w3id.org/rdip/graph"
SHACL_DIR  = Path(__file__).parent / "shacl"
SPARQL_DIR = Path(__file__).parent / "sparql"


def conflict_graph_uri(study_id: str) -> str:
    return f"{GRAPH_BASE}/{study_id}/conflicts"


def _load_sparql(filename: str) -> str:
    path = SPARQL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"SPARQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def _load_shacl_graph() -> Graph:
    """Load and merge all SHACL shapes into one rdflib Graph."""
    g = Graph()
    for ttl_file in SHACL_DIR.glob("*.ttl"):
        g.parse(str(ttl_file), format="turtle")
    print(f"[DiffEngine] Loaded {len(g)} SHACL triples "
          f"from {len(list(SHACL_DIR.glob('*.ttl')))} shape files")
    return g


def _fetch_graph_as_turtle(graph_uri: str) -> str:
    """
    Fetch all triples from a named graph via SPARQL CONSTRUCT
    and return as Turtle string.
    """
    q = f"""
    CONSTRUCT {{ ?s ?p ?o }}
    WHERE {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}
    """
    result = sparql_query(q)
    # SPARQLWrapper returns RDF/XML by default for CONSTRUCT
    # Re-parse with rdflib for clean Turtle serialisation
    g = Graph()
    g.parse(data=str(result), format="xml")
    return g.serialize(format="turtle")


def _run_construct_query(query_template: str,
                         original_uri: str,
                         reproduction_uri: str) -> Graph:
    """
    Execute a SPARQL CONSTRUCT query with graph URIs substituted.
    Uses direct HTTP POST to Oxigraph with text/turtle Accept header.
    """
    # Substitute graph URI placeholders
    # The templates use ?originalGraph and ?reproductionGraph as
    # bare names — replace with quoted URI literals
    query = query_template
    query = query.replace(
        "GRAPH ?originalGraph",
        f"GRAPH <{original_uri}>"
    )
    query = query.replace(
        "GRAPH ?reproductionGraph",
        f"GRAPH <{reproduction_uri}>"
    )

    # Remove the BIND lines that reference the old variables
    # since they are now hardcoded URIs
    filtered_lines = []
    for line in query.splitlines():
        skip = any(x in line for x in [
            "?originalGraph",
            "?reproductionGraph",
        ])
        if not skip:
            filtered_lines.append(line)
    query = "\n".join(filtered_lines)

    try:
        return sparql_construct(query)
    except Exception as e:
        print(f"[DiffEngine] CONSTRUCT error: {e}")
        return Graph()


def _run_shacl_validation(data_graph_uri: str) -> tuple[bool, Graph, str]:
    """
    Run pySHACL validation against a named graph.
    Fetches graph directly from Oxigraph store endpoint.
    """
    data_graph = fetch_graph(data_graph_uri)

    if len(data_graph) == 0:
        print(f"[DiffEngine] WARNING: Empty graph for {data_graph_uri}")
        return True, Graph(), "Empty graph — no triples to validate"

    shacl_graph = _load_shacl_graph()

    conforms, results_graph, results_text = validate(
        data_graph,
        shacl_graph=shacl_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_warnings=True,
        meta_shacl=False,
    )
    return conforms, results_graph, results_text


def _parse_shacl_results(results_text: str) -> list[dict]:
    violations = []
    if not results_text or "Conforms: True" in results_text:
        return violations

    blocks = results_text.split("Constraint Violation")
    for block in blocks[1:]:
        violation = {
            "severity": "UNKNOWN",
            "message":  "",
            "path":     "",
            "focus":    "",
        }
        for line in block.splitlines():
            line = line.strip()
            if "Severity:" in line:
                violation["severity"] = (
                    "CRITICAL" if "Violation" in line else "WARNING"
                )
            elif "Message:" in line:
                violation["message"] = line.split("Message:", 1)[-1].strip()
            elif "Result Path:" in line:
                violation["path"] = line.split("Result Path:", 1)[-1].strip()
            elif "Focus Node:" in line:
                violation["focus"] = line.split("Focus Node:", 1)[-1].strip()
        violations.append(violation)

    return violations


def run_diff(original_study_id: str,
             reproduction_study_id: str) -> dict:
    orig_uri = f"{GRAPH_BASE}/{original_study_id}"
    repr_uri = f"{GRAPH_BASE}/{reproduction_study_id}"
    conf_uri = conflict_graph_uri(original_study_id)

    print(f"\n[DiffEngine] === Semantic Diff ===")
    print(f"[DiffEngine] Original:     {orig_uri}")
    print(f"[DiffEngine] Reproduction: {repr_uri}")

    # Stage 1: verify both graphs exist
    if not graph_exists(orig_uri):
        return {"status": "error",
                "message": f"Original graph not found: {orig_uri}"}
    if not graph_exists(repr_uri):
        return {"status": "error",
                "message": f"Reproduction graph not found: {repr_uri}"}

    orig_triples = count_triples(orig_uri)
    repr_triples = count_triples(repr_uri)
    print(f"[DiffEngine] Original:     {orig_triples} triples")
    print(f"[DiffEngine] Reproduction: {repr_triples} triples")

    # Stage 2: SPARQL CONSTRUCT conflict materialisation
    all_conflicts   = Graph()
    all_conflicts.bind("rdip", RDIP)
    conflict_counts = {
        "version_conflicts": 0,
        "digest_conflicts":  0,
        "seed_conflicts":    0,
    }

    for filename, key in [
        ("construct_version_conflicts.sparql", "version_conflicts"),
        ("construct_digest_conflicts.sparql",  "digest_conflicts"),
        ("construct_seed_conflicts.sparql",    "seed_conflicts"),
    ]:
        try:
            query    = _load_sparql(filename)
            result_g = _run_construct_query(query, orig_uri, repr_uri)
            n        = len(result_g)
            conflict_counts[key] = n
            print(f"[DiffEngine] {key}: {n} triples")
            for triple in result_g:
                all_conflicts.add(triple)
        except Exception as e:
            print(f"[DiffEngine] Error running {filename}: {e}")

    if len(all_conflicts) > 0:
        upload_graph(conf_uri, all_conflicts.serialize(format="turtle"))
        print(f"[DiffEngine] Conflict graph uploaded → {count_triples(conf_uri)} triples")
    else:
        print(f"[DiffEngine] No Stage 2 conflicts detected")

    # Stage 3: SHACL validation
    print(f"\n[DiffEngine] Running SHACL validation ...")
    conforms, results_graph, results_text = _run_shacl_validation(repr_uri)
    violations = _parse_shacl_results(results_text)

    critical = [v for v in violations if v["severity"] == "CRITICAL"]
    warnings = [v for v in violations if v["severity"] == "WARNING"]

    print(f"[DiffEngine] SHACL: conforms={conforms} | "
          f"critical={len(critical)} warnings={len(warnings)}")

    return {
        "status":                  "ok",
        "original_study_id":       original_study_id,
        "reproduction_study_id":   reproduction_study_id,
        "original_triples":        orig_triples,
        "reproduction_triples":    repr_triples,
        "conflict_graph_uri":      conf_uri,
        "conflict_counts":         conflict_counts,
        "shacl_conforms":          conforms,
        "shacl_violations": {
            "critical": critical,
            "warnings": warnings,
        },
        "stage2_conflicts": sum(conflict_counts.values()),
        "stage3_critical":  len(critical),
        "total_conflicts":  sum(conflict_counts.values()) + len(critical),
    }