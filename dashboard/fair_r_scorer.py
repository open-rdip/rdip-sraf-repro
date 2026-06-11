# dashboard/fair_r_scorer.py
"""
FAIR-R Scoring Model — OB3 (standards-grounded rebuild).

Scoring is derived from published standards rather than ad-hoc weights
(see docs/fair_r_scoring_rubric.md):

  - Within a dimension, each criterion's weight comes from its RDA FAIR Data
    Maturity Model priority:  essential = 3, important = 2, useful = 1.
    criterion_max = (priority / sum of priorities in the dimension) x dimension_max.
  - Each criterion earns a GRADED level (F-UJI-style maturity), not yes/no:
        absent = 0.0 x max,  partial (present) = 0.5 x max,  full = 1.0 x max.
    "full" means machine-readable / standard-conformant (e.g. an SPDX licence,
    a recognised PID scheme), "partial" means merely present.
  - The Reproducible dimension uses explicit sub-weights (R1 0.4, R2 0.3, R3 0.3)
    and is grounded in the ML Reproducibility Checklist + FAIR4RS.
  - Cross-dimension weights start from the standards and are refined empirically
    by the RQ4 regression.

Levels are evaluated with SPARQL ASK queries against the study's named graph:
a `present` query (level >= 1) and an optional `full` query (level 2).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from triplestore_client import sparql_query

GRAPH_BASE = "https://w3id.org/rdip/graph"

PREFIXES = (
    "PREFIX rdip: <https://w3id.org/rdip/> "
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
)

PRIORITY_WEIGHT = {"essential": 3, "important": 2, "useful": 1}
LEVEL_FACTOR = {0: 0.0, 1: 0.5, 2: 1.0}
LEVEL_NAME = {0: "absent", 1: "partial", 2: "full"}


# -----------------------------------------------------------------------------
# Rubric — every criterion maps to a standard and carries a priority.
#   present : ASK that is true when the criterion is present at all (level 1)
#   full    : ASK that is true when present AND machine-readable/standard (level 2);
#             None means "present implies full".
#   fraction: (Reproducible only) explicit share of the dimension max.
# -----------------------------------------------------------------------------
DIMENSIONS = {
    "Findable": {
        "max_score": 15,
        "criteria": [
            {
                "label": "Persistent identifier",
                "priority": "essential", "standard": "RDA-F1-01M / FsF-F1-02D",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:identifier ?o }} }}",
                "full": ("ASK {{ GRAPH <{g}> {{ ?s rdip:identifier ?o FILTER("
                         "CONTAINS(LCASE(STR(?o)),\"doi.org\") || "
                         "CONTAINS(LCASE(STR(?o)),\"handle.net\") || "
                         "CONTAINS(LCASE(STR(?o)),\"zenodo\") || "
                         "CONTAINS(LCASE(STR(?o)),\"w3id.org\") || "
                         "CONTAINS(STR(?o),\"10.\")) }} }}"),
                "fix": "Declare a persistent identifier (DOI / Handle), not just a repository URL.",
            },
            {
                "label": "Descriptive metadata",
                "priority": "essential", "standard": "RDA-F2-01M / FsF-F2-01M",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdfs:label ?o }} }}",
                "full": None,
                "fix": "Provide core descriptive metadata (title, creator, date, keywords).",
            },
            {
                "label": "Landing page",
                "priority": "important", "standard": "RDA-F3-01M / FsF-F3-01M",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:datasetLandingPage ?o }} }}",
                "full": None,
                "fix": "Link a landing page where the dataset can be accessed.",
            },
        ],
    },
    "Accessible": {
        "max_score": 15,
        "criteria": [
            {
                "label": "Access protocol",
                "priority": "essential", "standard": "RDA-A1-02M / FsF-A1-02M",
                "present": ("ASK {{ GRAPH <{g}> {{ ?s rdip:identifier ?o "
                            "FILTER(STRSTARTS(LCASE(STR(?o)),\"http\")) }} }}"),
                "full": None,
                "fix": "Expose the artifact over a standard protocol (HTTP/S) via a resolvable identifier.",
            },
            {
                "label": "Data licence",
                "priority": "essential", "standard": "RDA-A1.1-01M / FsF-R1.1-01M",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:dataLicense ?o }} }}",
                "full": None,
                "fix": "Declare a machine-readable data licence (SPDX identifier).",
            },
            {
                "label": "Access level",
                "priority": "important", "standard": "RDA-A1-01M / FsF-A1-01M",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:accessLevel ?o }} }}",
                "full": ("ASK {{ GRAPH <{g}> {{ ?s rdip:accessLevel ?o FILTER("
                         "LCASE(STR(?o)) IN (\"open\",\"public\",\"restricted\","
                         "\"embargoed\",\"closed\")) }} }}"),
                "fix": "Declare the access level using a controlled vocabulary (open/restricted/embargoed).",
            },
        ],
    },
    "Interoperable": {
        "max_score": 20,
        "criteria": [
            {
                "label": "Method declared",
                "priority": "important", "standard": "RDA-I1-01M / FsF-I1-01M",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:usedMethod ?o }} }}",
                "full": None,
                "fix": "Link the activity to an rdip:Method describing the algorithm used.",
            },
            {
                "label": "Workflow language",
                "priority": "important", "standard": "RDA-I2-01M / FsF-I1-02M",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:workflowLanguage ?o }} }}",
                "full": None,
                "fix": "Declare the workflow language (Python, Snakemake, Nextflow, …).",
            },
            {
                "label": "Related links",
                "priority": "useful", "standard": "RDA-I3-01M / FsF-I3-01M",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:isRelatedTo ?o }} }}",
                "full": None,
                "fix": "Link related entities (datasets, publications) via typed relations.",
            },
        ],
    },
    "Reusable": {
        "max_score": 20,
        "criteria": [
            {
                "label": "Software licence",
                "priority": "essential", "standard": "RDA-R1.1-01M / FAIR4RS-R",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:softwareLicense ?o }} }}",
                "full": ("ASK {{ GRAPH <{g}> {{ ?s rdip:softwareLicense ?o FILTER("
                         "?o != \"LicenseRef-Custom\" && STR(?o) != \"\") }} }}"),
                "fix": "Add a standard (SPDX) software licence to the repository.",
            },
            {
                "label": "Commit + versioning",
                "priority": "important", "standard": "RDA-R1.2-01M / FAIR4RS",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:commitHash ?o }} }}",
                "full": None,
                "fix": "Record the release commit SHA (and a tagged version).",
            },
            {
                "label": "Community standard",
                "priority": "useful", "standard": "RDA-R1.3-01M / FsF-R1.3-01M",
                "present": "ASK {{ GRAPH <{g}> {{ ?s rdip:conformsTo ?o }} }}",
                "full": None,
                "fix": "Adopt a community metadata / file-format standard.",
            },
        ],
    },
    "Reproducible": {
        "max_score": 30,
        "criteria": [
            {
                "label": "Computational environment (R1)",
                "fraction": 0.4, "standard": "ML Repro Checklist; FAIR4RS",
                "present": ("ASK {{ GRAPH <{g}> {{ {{ ?s a rdip:EnvironmentSpec }} "
                            "UNION {{ ?s rdip:softwareDependency ?d }} }} }}"),
                "full": ("ASK {{ GRAPH <{g}> {{ ?s rdip:imageDigest ?o "
                         "FILTER(STR(?o) != \"\") }} }}"),
                "fix": "Pin the environment: image digest (FROM …@sha256) and exact dependency versions.",
            },
            {
                "label": "Methodological transparency (R2)",
                "fraction": 0.3, "standard": "ML Repro Checklist (hyperparams, seeds)",
                "present": ("ASK {{ GRAPH <{g}> {{ {{ ?s a rdip:RandomSeed }} "
                            "UNION {{ ?s rdip:hasParameter ?p }} "
                            "UNION {{ ?s rdip:usedMethod ?m }} }} }}"),
                "full": ("ASK {{ GRAPH <{g}> {{ ?s a rdip:RandomSeed . "
                         "?a rdip:usedMethod ?m }} }}"),
                "fix": "Declare random seeds, hyperparameters, and methods/algorithms.",
            },
            {
                "label": "Data provenance (R3)",
                "fraction": 0.3, "standard": "ML Repro Checklist (data, splits, eval)",
                "present": ("ASK {{ GRAPH <{g}> {{ {{ ?s a rdip:EvaluationResult }} "
                            "UNION {{ ?s a rdip:Dataset }} }} }}"),
                "full": ("ASK {{ GRAPH <{g}> {{ ?s a rdip:EvaluationResult . "
                         "?d a rdip:Dataset }} }}"),
                "fix": "Record dataset identity, train/val/test splits, preprocessing, and evaluation results.",
            },
        ],
    },
}

# Tier thresholds (0-100)
TIERS = [(85, "excellent"), (70, "good"), (50, "fair"), (0, "poor")]


# ── Scoring logic ─────────────────────────────────────────────────────────────

def _ask(query_template: str, graph_uri: str) -> bool:
    try:
        result = sparql_query(PREFIXES + query_template.format(g=graph_uri))
        return result.get("boolean", False)
    except Exception as e:  # noqa: BLE001
        print(f"  [Scorer] ASK error: {e}")
        return False


def _grade(graph_uri: str, criterion: dict) -> int:
    """Return maturity level 0 (absent), 1 (partial), 2 (full)."""
    if not _ask(criterion["present"], graph_uri):
        return 0
    if criterion.get("full") is None:
        return 2
    return 2 if _ask(criterion["full"], graph_uri) else 1


def _criterion_max(criterion: dict, dim: dict) -> float:
    """Max points for a criterion: explicit fraction, or RDA-priority share."""
    if "fraction" in criterion:
        return criterion["fraction"] * dim["max_score"]
    total = sum(PRIORITY_WEIGHT[c["priority"]] for c in dim["criteria"]
                if "priority" in c)
    return PRIORITY_WEIGHT[criterion["priority"]] / total * dim["max_score"]


def compute_fair_r(study_id: str) -> dict:
    """Compute the graded, standards-weighted FAIR-R score for a study."""
    graph_uri = f"{GRAPH_BASE}/{study_id}"
    print(f"\n[Scorer] Computing FAIR-R for {study_id}  <{graph_uri}>")

    total_score = 0.0
    dimension_scores = {}
    recommendations = []

    for dim_name, dim in DIMENSIONS.items():
        dim_score = 0.0
        criteria_results = []
        for c in dim["criteria"]:
            c_max = _criterion_max(c, dim)
            level = _grade(graph_uri, c)
            points = LEVEL_FACTOR[level] * c_max
            dim_score += points

            criteria_results.append({
                "label": c["label"],
                "priority": c.get("priority", "—"),
                "standard": c.get("standard", ""),
                "level": LEVEL_NAME[level],
                "points": round(points, 2),
                "max": round(c_max, 2),
                "fix": c["fix"] if level < 2 else None,
            })

            if level < 2:
                recommendations.append({
                    "dimension": dim_name,
                    "label": c["label"],
                    "priority": c.get("priority", "—"),
                    "level": LEVEL_NAME[level],
                    "fix": c["fix"],
                    "points_available": round(c_max - points, 2),
                })

            print(f"  [{LEVEL_NAME[level]:7s}] {dim_name:14s} | {c['label']:32s} "
                  f"+{points:.1f}/{c_max:.1f}")

        total_score += dim_score
        dimension_scores[dim_name] = {
            "score": round(dim_score, 2),
            "max": dim["max_score"],
            "percent": round(dim_score / dim["max_score"] * 100, 1),
            "criteria": criteria_results,
        }

    total_score = round(total_score, 2)
    tier = next(name for thr, name in TIERS if total_score >= thr)

    # Recommendations: essential gaps first, then by points recoverable.
    prio_rank = {"essential": 0, "important": 1, "useful": 2, "—": 3}
    recommendations.sort(key=lambda r: (prio_rank.get(r["priority"], 3),
                                        -r["points_available"]))

    print(f"\n[Scorer] FAIR-R: {total_score}/100 — {tier.upper()}")
    return {
        "study_id": study_id,
        "graph_uri": graph_uri,
        "total_score": total_score,
        "tier": tier,
        "dimension_scores": dimension_scores,
        "recommendations": recommendations,
    }


def score_summary(result: dict) -> str:
    dims = result["dimension_scores"]
    parts = " | ".join(f"{k[:2]}: {v['score']}/{v['max']}" for k, v in dims.items())
    return (f"FAIR-R={result['total_score']}/100 "
            f"[{result['tier'].upper()}] — {parts}")
