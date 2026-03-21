# lifter/mapper/rdip_mapper.py
"""
Maps normalised parser output into RDIP v2.0 RDF triples.
All output is returned as rdflib Graph objects and serialised to Turtle.
"""

import uuid
from rdflib import Graph, Namespace, URIRef, Literal, RDF, XSD

RDIP  = Namespace("https://w3id.org/rdip/")
PROV  = Namespace("http://www.w3.org/ns/prov#")
DCAT  = Namespace("http://www.w3.org/ns/dcat#")
RDFS  = Namespace("http://www.w3.org/2000/01/rdf-schema#")

BASE  = "https://w3id.org/rdip/instance/"


def mint(prefix: str) -> URIRef:
    """Mint a fresh, unique URI for a new entity."""
    return URIRef(f"{BASE}{prefix}-{uuid.uuid4().hex[:10]}")


def study_uri(study_id: str) -> URIRef:
    return URIRef(f"{BASE}activity-{study_id}")


def software_uri(study_id: str) -> URIRef:
    return URIRef(f"{BASE}software-{study_id}")


def env_uri(study_id: str) -> URIRef:
    return URIRef(f"{BASE}env-{study_id}")


def envspec_uri(study_id: str) -> URIRef:
    return URIRef(f"{BASE}envspec-{study_id}")


# ── Namespace bindings ───────────────────────────────────────────────────────

def _base_graph() -> Graph:
    g = Graph()
    g.bind("rdip",  RDIP)
    g.bind("prov",  PROV)
    g.bind("dcat",  DCAT)
    g.bind("xsd",   XSD)
    return g


# ── Docker → RDIP ────────────────────────────────────────────────────────────

def map_docker(study_id: str, parsed: dict) -> Graph:
    """
    Map parsed Docker data to RDIP triples.
    Produces:
      rdip:ResearchActivity → rdip:executedIn → rdip:ComputingEnvironment
      rdip:ComputingEnvironment → rdip:hasEnvironmentSpec → rdip:EnvironmentSpec
    """
    g       = _base_graph()
    activity = study_uri(study_id)
    env      = env_uri(study_id)
    env_spec = envspec_uri(study_id)

    # ResearchActivity
    g.add((activity, RDF.type,          RDIP.ResearchActivity))
    g.add((activity, RDIP.executedIn,   env))

    # ComputingEnvironment
    g.add((env, RDF.type, RDIP.ComputingEnvironment))
    g.add((env, RDIP.hasEnvironmentSpec, env_spec))

    if parsed.get("os"):
        g.add((env, RDIP.osVersion,
               Literal(parsed["os"], datatype=XSD.string)))
    if parsed.get("architecture"):
        g.add((env, RDIP.hardwareSpec,
               Literal(parsed["architecture"], datatype=XSD.string)))
    if parsed.get("cuda_version"):
        g.add((env, RDIP.cudaVersion,
               Literal(parsed["cuda_version"], datatype=XSD.string)))

    # EnvironmentSpec
    g.add((env_spec, RDF.type,      RDIP.EnvironmentSpec))
    g.add((env_spec, RDIP.specType, Literal("docker", datatype=XSD.string)))

    if parsed.get("image_digest"):
        g.add((env_spec, RDIP.imageDigest,
               Literal(parsed["image_digest"], datatype=XSD.string)))
    if parsed.get("spec_uri"):
        g.add((env_spec, RDIP.specUri,
               Literal(parsed["spec_uri"], datatype=XSD.anyURI)))

    return g


# ── Conda → RDIP ─────────────────────────────────────────────────────────────

def map_conda(study_id: str, parsed: dict) -> Graph:
    """
    Map parsed Conda data to RDIP triples.
    Produces:
      rdip:SoftwareApplication → rdip:softwareDependency → rdip:SoftwareDependency (×n)
      rdip:SoftwareApplication → rdip:hasEnvironmentSpec → rdip:EnvironmentSpec
    """
    g        = _base_graph()
    activity  = study_uri(study_id)
    software  = software_uri(study_id)
    env_spec  = envspec_uri(study_id)

    # Link activity → software
    g.add((activity, RDF.type,         RDIP.ResearchActivity))
    g.add((activity, RDIP.usedSoftware, software))

    # SoftwareApplication
    g.add((software, RDF.type,               RDIP.SoftwareApplication))
    g.add((software, RDIP.hasEnvironmentSpec, env_spec))

    # EnvironmentSpec
    g.add((env_spec, RDF.type,      RDIP.EnvironmentSpec))
    g.add((env_spec, RDIP.specType, Literal("conda", datatype=XSD.string)))
    if parsed.get("spec_uri"):
        g.add((env_spec, RDIP.specUri,
               Literal(parsed["spec_uri"], datatype=XSD.anyURI)))

    # Conda dependencies
    for dep in parsed.get("dependencies", []):
        _add_dependency(g, software, dep, "conda")

    # Pip dependencies inside the conda env
    for dep in parsed.get("pip_dependencies", []):
        _add_dependency(g, software, dep, "pip")

    return g


# ── Pip → RDIP ───────────────────────────────────────────────────────────────

def map_pip(study_id: str, parsed: dict) -> Graph:
    """
    Map parsed pip requirements to RDIP triples.
    Produces:
      rdip:SoftwareApplication → rdip:softwareDependency → rdip:SoftwareDependency (×n)
    """
    g        = _base_graph()
    activity  = study_uri(study_id)
    software  = software_uri(study_id)

    g.add((activity, RDF.type,          RDIP.ResearchActivity))
    g.add((activity, RDIP.usedSoftware, software))
    g.add((software, RDF.type,          RDIP.SoftwareApplication))

    for dep in parsed.get("dependencies", []):
        _add_dependency(g, software, dep, "pip")

    return g


# ── Shared helpers ────────────────────────────────────────────────────────────

def _add_dependency(g: Graph, software: URIRef,
                    dep: dict, dep_type: str):
    """Add a single SoftwareDependency node linked to a SoftwareApplication."""
    dep_node = mint("dep")
    g.add((dep_node, RDF.type,
           RDIP.SoftwareDependency))
    g.add((dep_node, RDIP.dependencyName,
           Literal(dep["name"], datatype=XSD.string)))
    g.add((dep_node, RDIP.dependencyVersion,
           Literal(dep.get("version", "unspecified"), datatype=XSD.string)))
    g.add((dep_node, RDIP.dependencyType,
           Literal(dep_type, datatype=XSD.string)))
    g.add((software, RDIP.softwareDependency, dep_node))


# ── Merge and serialise ───────────────────────────────────────────────────────

def merge_graphs(*graphs: Graph) -> Graph:
    """Merge multiple rdflib Graphs into one."""
    merged = _base_graph()
    for g in graphs:
        for triple in g:
            merged.add(triple)
    return merged


def to_turtle(g: Graph) -> str:
    """Serialise a graph to a Turtle string."""
    return g.serialize(format="turtle")
