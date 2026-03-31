# dashboard/fair_r_scorer.py
"""
FAIR-R Scoring Model — OB3.

Computes a quantitative FAIR-R score (0-100) for a study
by querying its named graph in Oxigraph and checking
which RDIP metadata criteria are satisfied.

Five dimensions:
  Findable      (max 15) — identifier + landing page
  Accessible    (max 15) — access level + license
  Interoperable (max 20) — method + workflow language
  Reusable      (max 20) — software license + commit hash
  Reproducible  (max 30) — image digest + random seed + evaluation result

Each criterion is checked by a SPARQL ASK query.
Score = sum of (criterion_weight * max_dimension_score)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from triplestore_client import sparql_query

RDIP      = "https://w3id.org/rdip/"
GRAPH_BASE = "https://w3id.org/rdip/graph"


# ── Scoring model ─────────────────────────────────────────────────────────────
# Each criterion: (label, sparql_ask_template, weight_within_dimension, severity)
# Weights within a dimension sum to 1.0
# severity: "critical" = blocks full tier, "warning" = informational

DIMENSIONS = {
    "Findable": {
        "max_score": 15,
        "weight":    0.15,
        "criteria": [
            {
                "label":    "Persistent identifier declared",
                "property": "rdip:identifier",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s <{rdip}identifier> ?o }} }}",
                "weight":   0.5,
                "severity": "critical",
                "fix":      "Add rdip:identifier to your ResearchProject node. Use your paper DOI or repository URL.",
            },
            {
                "label":    "Dataset landing page declared",
                "property": "rdip:datasetLandingPage",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s <{rdip}datasetLandingPage> ?o }} }}",
                "weight":   0.5,
                "severity": "warning",
                "fix":      "Add rdip:datasetLandingPage linking to where your dataset can be accessed.",
            },
        ]
    },
    "Accessible": {
        "max_score": 15,
        "weight":    0.15,
        "criteria": [
            {
                "label":    "Access level declared",
                "property": "rdip:accessLevel",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s <{rdip}accessLevel> ?o }} }}",
                "weight":   0.5,
                "severity": "warning",
                "fix":      "Declare rdip:accessLevel (open, restricted, or embargoed).",
            },
            {
                "label":    "Data license declared",
                "property": "rdip:dataLicense",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s <{rdip}dataLicense> ?o }} }}",
                "weight":   0.5,
                "severity": "critical",
                "fix":      "Add a LICENSE file and declare rdip:dataLicense with a SPDX identifier (e.g. CC-BY-4.0).",
            },
        ]
    },
    "Interoperable": {
        "max_score": 20,
        "weight":    0.20,
        "criteria": [
            {
                "label":    "Method declared",
                "property": "rdip:usedMethod",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s <{rdip}usedMethod> ?o }} }}",
                "weight":   0.5,
                "severity": "warning",
                "fix":      "Link your ResearchActivity to an rdip:Method instance describing the algorithm used.",
            },
            {
                "label":    "Workflow language declared",
                "property": "rdip:workflowLanguage",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s <{rdip}workflowLanguage> ?o }} }}",
                "weight":   0.5,
                "severity": "warning",
                "fix":      "Declare rdip:workflowLanguage on your Method (e.g. Python, Snakemake, Nextflow).",
            },
        ]
    },
    "Reusable": {
        "max_score": 20,
        "weight":    0.20,
        "criteria": [
            {
                "label":    "Software license declared",
                "property": "rdip:softwareLicense",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s <{rdip}softwareLicense> ?o }} }}",
                "weight":   0.5,
                "severity": "critical",
                "fix":      "Add a software license to your repository and declare rdip:softwareLicense.",
            },
            {
                "label":    "Commit hash recorded",
                "property": "rdip:commitHash",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s <{rdip}commitHash> ?o }} }}",
                "weight":   0.5,
                "severity": "critical",
                "fix":      "Tag your release commit and record the SHA as rdip:commitHash.",
            },
        ]
    },
    "Reproducible": {
        "max_score": 30,
        "weight":    0.30,
        "criteria": [
            {
                "label":    "Image digest pinned",
                "property": "rdip:imageDigest",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s <{rdip}imageDigest> ?o . FILTER(?o != \"\") }} }}",
                "weight":   0.4,
                "severity": "critical",
                "fix":      "Pin your Docker image to a specific digest: FROM image@sha256:<digest>.",
            },
            {
                "label":    "Random seed declared",
                "property": "rdip:RandomSeed",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s a <{rdip}RandomSeed> }} }}",
                "weight":   0.3,
                "severity": "critical",
                "fix":      "Declare all random seeds used in training or data splitting as rdip:RandomSeed instances.",
            },
            {
                "label":    "Evaluation result linked",
                "property": "rdip:EvaluationResult",
                "ask":      "ASK {{ GRAPH <{graph}> {{ ?s a <{rdip}EvaluationResult> }} }}",
                "weight":   0.3,
                "severity": "warning",
                "fix":      "Link your reported metrics to rdip:EvaluationResult instances with rdip:metricName and rdip:metricValue.",
            },
        ]
    },
}


# ── Scoring logic ─────────────────────────────────────────────────────────────

def _check_criterion(graph_uri: str, criterion: dict) -> bool:
    """Run a single SPARQL ASK query. Returns True if criterion is met."""
    ask_query = criterion["ask"].format(
        graph=graph_uri,
        rdip=RDIP
    )
    try:
        result = sparql_query(ask_query)
        return result.get("boolean", False)
    except Exception as e:
        print(f"  [Scorer] Error checking {criterion['label']}: {e}")
        return False


def compute_fair_r(study_id: str) -> dict:
    """
    Compute the FAIR-R score for a study.

    Returns a structured result dict containing:
      - total_score (0-100)
      - dimension_scores dict
      - criterion_results list
      - recommendations list
      - tier (excellent/good/fair/poor)
    """
    graph_uri = f"{GRAPH_BASE}/{study_id}"
    print(f"\n[Scorer] Computing FAIR-R score for {study_id}")
    print(f"[Scorer] Graph: {graph_uri}")

    total_score       = 0.0
    dimension_scores  = {}
    criterion_results = []
    recommendations   = []

    for dim_name, dim in DIMENSIONS.items():
        dim_score        = 0.0
        dim_max          = dim["max_score"]
        criteria_results = []

        for criterion in dim["criteria"]:
            met   = _check_criterion(graph_uri, criterion)
            # Score contribution: criterion weight × dimension max score
            points = criterion["weight"] * dim_max if met else 0.0

            dim_score += points
            criteria_results.append({
                "label":    criterion["label"],
                "property": criterion["property"],
                "met":      met,
                "points":   round(points, 2),
                "max":      round(criterion["weight"] * dim_max, 2),
                "severity": criterion["severity"],
                "fix":      criterion["fix"] if not met else None,
            })

            if not met:
                recommendations.append({
                    "dimension": dim_name,
                    "severity":  criterion["severity"],
                    "label":     criterion["label"],
                    "fix":       criterion["fix"],
                })

            status = "✓" if met else "✗"
            print(f"  [{status}] {dim_name:14s} | "
                  f"{criterion['label']:40s} "
                  f"+{points:.1f}/{criterion['weight'] * dim_max:.1f}")

        dimension_scores[dim_name] = {
            "score":    round(dim_score, 2),
            "max":      dim_max,
            "percent":  round((dim_score / dim_max) * 100, 1),
            "criteria": criteria_results,
        }
        total_score += dim_score

    total_score = round(total_score, 2)

    # Determine tier
    if total_score >= 85:
        tier = "excellent"
    elif total_score >= 70:
        tier = "good"
    elif total_score >= 50:
        tier = "fair"
    else:
        tier = "poor"

    # Sort recommendations — critical first
    recommendations.sort(
        key=lambda r: 0 if r["severity"] == "critical" else 1
    )

    print(f"\n[Scorer] FAIR-R Score: {total_score}/100 — {tier.upper()}")

    return {
        "study_id":         study_id,
        "graph_uri":        graph_uri,
        "total_score":      total_score,
        "tier":             tier,
        "dimension_scores": dimension_scores,
        "recommendations":  recommendations,
    }


def score_summary(result: dict) -> str:
    """Return a compact one-line summary of a FAIR-R result."""
    dims = result["dimension_scores"]
    parts = " | ".join(
        f"{k[:2]}: {v['score']}/{v['max']}"
        for k, v in dims.items()
    )
    return (f"FAIR-R={result['total_score']}/100 "
            f"[{result['tier'].upper()}] — {parts}")
