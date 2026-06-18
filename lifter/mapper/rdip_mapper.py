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

# ── maDMP → RDIP ─────────────────────────────────────────────────────────────

def map_dmp(study_id: str, parsed: dict) -> Graph:
    """
    Map parsed maDMP data to RDIP triples.
    DMP commitments become verifiable assertions in the KG.
    Produces:
      rdip:ResearchActivity → rdip:identifier (from DMP ID)
      rdip:ResearchActivity → rdip:generatesDataset → dcat:Dataset (×n)
      dcat:Dataset → rdip:dataLicense, rdip:accessLevel, rdip:datasetLandingPage
    """
    g        = _base_graph()
    activity = study_uri(study_id)

    g.add((activity, RDF.type, RDIP.ResearchActivity))

    # DMP identifier
    if parsed.get("dmp_id"):
        g.add((activity, RDIP.identifier,
               Literal(parsed["dmp_id"], datatype=XSD.string)))

    # Dataset commitments from DMP
    for i, ds in enumerate(parsed.get("datasets", [])):
        ds_node = URIRef(f"{BASE}dataset-{study_id}-{i}")
        g.add((ds_node, RDF.type, DCAT.Dataset))
        g.add((activity, RDIP.generatesDataset, ds_node))

        if ds.get("dataset_id"):
            g.add((ds_node, RDIP.identifier,
                   Literal(ds["dataset_id"], datatype=XSD.string)))

        if ds.get("title"):
            g.add((ds_node, RDFS.label,
                   Literal(ds["title"], datatype=XSD.string)))

        for dist in ds.get("distributions", []):
            if dist.get("license"):
                g.add((ds_node, RDIP.dataLicense,
                       URIRef(dist["license"])))
            if dist.get("data_access"):
                g.add((ds_node, RDIP.accessLevel,
                       Literal(dist["data_access"], datatype=XSD.string)))
            if dist.get("access_url"):
                g.add((ds_node, RDIP.datasetLandingPage,
                       URIRef(dist["access_url"])))

    return g


# ── Repository metadata → RDIP ───────────────────────────────────────────────

def map_repo_metadata(study_id: str, meta: dict) -> Graph:
    """Map repo-level metadata recoverable WITHOUT an LLM into RDIP triples.

    Feeds three FAIR-R criteria directly from the clone + corpus row:
      rdip:identifier      (Findable)  ← paper/repo URL
      rdip:softwareLicense (Reusable)  ← SPDX from LICENSE detection
      rdip:commitHash      (Reusable)  ← git rev-parse HEAD
    Attached to the same activity / software nodes the env-file maps use, so
    everything stays in one connected per-study graph.
    """
    g        = _base_graph()
    activity = study_uri(study_id)
    software = software_uri(study_id)

    g.add((activity, RDF.type, RDIP.ResearchActivity))
    if meta.get("identifier"):
        g.add((activity, RDIP.identifier,
               Literal(meta["identifier"], datatype=XSD.anyURI)))

    has_software = False
    if meta.get("software_license"):
        g.add((software, RDIP.softwareLicense,
               Literal(meta["software_license"], datatype=XSD.string)))
        has_software = True
    if meta.get("commit_hash"):
        g.add((software, RDIP.commitHash,
               Literal(meta["commit_hash"], datatype=XSD.string)))
        has_software = True

    if has_software:
        g.add((software, RDF.type, RDIP.SoftwareApplication))
        g.add((activity, RDIP.usedSoftware, software))

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
