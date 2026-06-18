# rag_pipeline/mapper.py
"""
Maps structured LLM extraction output to RDIP v2.0 RDF triples.
Appends to an existing study graph rather than replacing it,
so Phase I and Phase II triples coexist in the same named graph.
"""

import uuid
from rdflib import Graph, Namespace, URIRef, Literal, RDF, XSD

RDIP = Namespace("https://w3id.org/rdip/")
PROV = Namespace("http://www.w3.org/ns/prov#")
DCAT = Namespace("http://www.w3.org/ns/dcat#")   # datasets are dcat:Dataset
BASE = "https://w3id.org/rdip/instance/"


def mint(prefix: str) -> URIRef:
    return URIRef(f"{BASE}{prefix}-{uuid.uuid4().hex[:10]}")


def activity_uri(study_id: str) -> URIRef:
    return URIRef(f"{BASE}activity-{study_id}")


def software_uri(study_id: str) -> URIRef:
    return URIRef(f"{BASE}software-{study_id}")


def env_uri(study_id: str) -> URIRef:
    return URIRef(f"{BASE}env-{study_id}")


def _base_graph() -> Graph:
    g = Graph()
    g.bind("rdip", RDIP)
    g.bind("prov", PROV)
    g.bind("xsd",  XSD)
    return g


def map_extraction(study_id: str, extracted: dict) -> Graph:
    """
    Map merged LLM extraction output to RDIP triples.

    Produces:
      - rdip:RandomSeed instances linked to rdip:ResearchActivity
      - rdip:Parameter instances (hyperparameters)
      - rdip:SoftwareDependency instances (from narrative)
      - rdip:ComputingEnvironment hardware properties
      - rdip:Method instances
      - dcat:Dataset instances (via rdip:usedDataset)
      - rdip:EvaluationResult instances (via rdip:generatesResult)
    """
    g        = _base_graph()
    activity = activity_uri(study_id)
    software = software_uri(study_id)
    env      = env_uri(study_id)

    # Ensure activity node exists
    g.add((activity, RDF.type, RDIP.DataAnalysisActivity))

    # ── Random seeds ──────────────────────────────────────────────────────────
    for seed_val in extracted.get("random_seeds", []):
        seed_node = mint("seed")
        g.add((seed_node, RDF.type,
               RDIP.RandomSeed))
        g.add((seed_node, RDIP.parameterName,
               Literal("random_seed", datatype=XSD.string)))
        g.add((seed_node, RDIP.parameterValue,
               Literal(str(seed_val), datatype=XSD.string)))
        g.add((seed_node, RDIP.parameterDataType,
               Literal("xsd:integer", datatype=XSD.string)))
        g.add((activity, RDIP.hasParameter, seed_node))

    # ── Hyperparameters ───────────────────────────────────────────────────────
    for param in extracted.get("hyperparameters", []):
        if not param.get("name"):
            continue
        param_node = mint("param")
        g.add((param_node, RDF.type,
               RDIP.Parameter))
        g.add((param_node, RDIP.parameterName,
               Literal(param["name"], datatype=XSD.string)))
        g.add((param_node, RDIP.parameterValue,
               Literal(str(param.get("value", "")), datatype=XSD.string)))
        g.add((activity, RDIP.hasParameter, param_node))

    # ── Dependencies from narrative (supplement Phase I) ─────────────────────
    for dep in extracted.get("dependencies", []):
        if not dep.get("name"):
            continue
        dep_node = mint("dep")
        g.add((dep_node, RDF.type,
               RDIP.SoftwareDependency))
        g.add((dep_node, RDIP.dependencyName,
               Literal(dep["name"].lower(), datatype=XSD.string)))
        g.add((dep_node, RDIP.dependencyVersion,
               Literal(dep.get("version", "unspecified"), datatype=XSD.string)))
        g.add((dep_node, RDIP.dependencyType,
               Literal("narrative", datatype=XSD.string)))
        g.add((software, RDIP.softwareDependency, dep_node))

    # ── Hardware from narrative ───────────────────────────────────────────────
    hw = extracted.get("hardware", {})
    if hw.get("gpu_model"):
        g.add((env, RDF.type, RDIP.ComputingEnvironment))
        g.add((env, RDIP.gpuModel,
               Literal(hw["gpu_model"], datatype=XSD.string)))
    if hw.get("cuda_version"):
        g.add((env, RDF.type, RDIP.ComputingEnvironment))
        g.add((env, RDIP.cudaVersion,
               Literal(hw["cuda_version"], datatype=XSD.string)))

    # ── Methods ───────────────────────────────────────────────────────────────
    for method in extracted.get("methods", []):
        if not method.get("name"):
            continue
        method_node = mint("method")
        g.add((method_node, RDF.type,
               RDIP.Method))
        g.add((method_node, RDIP.title,
               Literal(method["name"], datatype=XSD.string)))
        if method.get("description"):
            g.add((method_node, RDIP.description,
                   Literal(method["description"], datatype=XSD.string)))
        g.add((activity, RDIP.usedMethod, method_node))

    # ── Datasets (the schema extracted them; previously dropped) ──────────────
    # No rdip:Dataset class exists in the ontology; link via rdip:usedDataset
    # and describe with rdip:title / rdip:version (both ontology-valid).
    for ds in extracted.get("datasets", []):
        if not ds.get("name"):
            continue
        ds_node = mint("dataset")
        g.add((ds_node, RDF.type, DCAT.Dataset))
        g.add((activity, RDIP.usedDataset, ds_node))
        g.add((ds_node, RDIP.title,
               Literal(ds["name"], datatype=XSD.string)))
        if ds.get("version"):
            g.add((ds_node, RDIP.version,
                   Literal(str(ds["version"]), datatype=XSD.string)))

    # ── Evaluation results (the paper's claimed metrics) ──────────────────────
    # Ground truth for the result-reproducibility test: a reproducer compares
    # their re-run numbers against these. Linked via rdip:generatesResult.
    for ev in extracted.get("evaluation_results", []):
        if not ev.get("metric"):
            continue
        ev_node = mint("eval")
        g.add((ev_node, RDF.type, RDIP.EvaluationResult))
        g.add((ev_node, RDIP.metricName,
               Literal(ev["metric"], datatype=XSD.string)))
        if ev.get("value") not in (None, ""):
            g.add((ev_node, RDIP.metricValue,
                   Literal(str(ev["value"]), datatype=XSD.string)))
        if ev.get("split"):
            g.add((ev_node, RDIP.splitLabel,
                   Literal(ev["split"], datatype=XSD.string)))
        g.add((activity, RDIP.generatesResult, ev_node))

    return g


def to_turtle(g: Graph) -> str:
    return g.serialize(format="turtle")
