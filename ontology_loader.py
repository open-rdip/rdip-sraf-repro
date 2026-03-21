import os, json, hashlib, requests
from datetime import datetime
from rdflib import Graph, Namespace, URIRef
from triplestore_client import upload_graph, count_triples, sparql_query
from dotenv import load_dotenv

load_dotenv()

ONTOLOGY_URI = os.getenv("ONTOLOGY_URI", "https://w3id.org/rdip/")
SCHEMA_GRAPH  = os.getenv("SCHEMA_GRAPH",  "https://w3id.org/rdip/schema")
CACHE_DIR     = os.path.join(os.path.dirname(__file__), ".ontology_cache")
CACHE_TTL     = os.path.join(CACHE_DIR, "rdip.ttl")
CACHE_META    = os.path.join(CACHE_DIR, "meta.json")
OWL           = Namespace("http://www.w3.org/2002/07/owl#")

os.makedirs(CACHE_DIR, exist_ok=True)

def _fetch() -> str:
    print(f"[OntologyLoader] Fetching {ONTOLOGY_URI} ...")
    r = requests.get(
        ONTOLOGY_URI,
        headers={"Accept": "text/turtle, application/x-turtle;q=0.9"},
        timeout=30,
        allow_redirects=True
    )
    r.raise_for_status()
    return r.text

def _parse_version(turtle_str: str) -> dict:
    g = Graph()
    g.parse(data=turtle_str, format="turtle")
    version_info = version_iri = None
    for _, _, o in g.triples((URIRef(ONTOLOGY_URI), OWL.versionInfo, None)):
        version_info = str(o)
    for _, _, o in g.triples((URIRef(ONTOLOGY_URI), OWL.versionIRI, None)):
        version_iri = str(o)
    return {
        "version_info": version_info,
        "version_iri":  version_iri,
        "checksum":     hashlib.sha256(turtle_str.encode()).hexdigest(),
    }

def _load_cached_meta() -> dict:
    if os.path.exists(CACHE_META):
        with open(CACHE_META) as f:
            return json.load(f)
    return {}

def _save_cache(turtle_str: str, meta: dict):
    with open(CACHE_TTL, "w") as f:
        f.write(turtle_str)
    meta["cached_at"] = datetime.utcnow().isoformat()
    with open(CACHE_META, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[OntologyLoader] Cache updated → version {meta.get('version_info')}")

def _is_newer(remote: dict, cached: dict) -> bool:
    if not cached:
        return True
    if remote.get("version_iri") and cached.get("version_iri"):
        return remote["version_iri"] != cached["version_iri"]
    if remote.get("version_info") and cached.get("version_info"):
        return remote["version_info"] != cached["version_info"]
    return remote["checksum"] != cached.get("checksum", "")

def _reload_into_triplestore(turtle_str: str):
    print("[OntologyLoader] Reloading schema graph ...")
    upload_graph(SCHEMA_GRAPH, turtle_str)
    print(f"[OntologyLoader] Schema graph has {count_triples(SCHEMA_GRAPH)} triples.")

def ensure_latest(force: bool = False) -> dict:
    cached_meta = _load_cached_meta()
    try:
        turtle_str  = _fetch()
        remote_meta = _parse_version(turtle_str)
    except requests.RequestException as e:
        print(f"[OntologyLoader] WARNING: {e} — falling back to cache.")
        if os.path.exists(CACHE_TTL):
            with open(CACHE_TTL) as f:
                turtle_str = f.read()
            _reload_into_triplestore(turtle_str)
            cached_meta["reloaded"] = True
            cached_meta["source"]   = "cache_fallback"
            return cached_meta
        raise RuntimeError("No network and no cache. Run once online first.")

    if force or _is_newer(remote_meta, cached_meta):
        print(f"[OntologyLoader] New version detected — "
              f"remote={remote_meta.get('version_info')} "
              f"cached={cached_meta.get('version_info')}")
        _reload_into_triplestore(turtle_str)
        _save_cache(turtle_str, remote_meta)
        remote_meta["reloaded"] = True
        remote_meta["source"]   = "remote"
        return remote_meta

    print(f"[OntologyLoader] Up to date "
          f"(version {cached_meta.get('version_info')}) — no reload needed.")
    cached_meta["reloaded"] = False
    cached_meta["source"]   = "cache"
    return cached_meta

def get_ontology_graph() -> Graph:
    if not os.path.exists(CACHE_TTL):
        raise RuntimeError("No cached ontology. Call ensure_latest() first.")
    g = Graph()
    g.parse(CACHE_TTL, format="turtle")
    return g