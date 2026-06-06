import os
import requests
from rdflib import Graph
from SPARQLWrapper import SPARQLWrapper, JSON
from dotenv import load_dotenv

load_dotenv()

from config import OXIGRAPH_URL as BASE_URL


def sparql_query(query: str) -> dict:
    sw = SPARQLWrapper(f"{BASE_URL}/query")
    sw.setQuery(query)
    sw.setReturnFormat(JSON)
    return sw.query().convert()


def sparql_construct(query: str) -> Graph:
    r = requests.post(
        f"{BASE_URL}/query",
        headers={
            "Content-Type": "application/sparql-query",
            "Accept":        "text/turtle",
        },
        data=query.encode("utf-8"),
        timeout=30
    )
    r.raise_for_status()
    g = Graph()
    g.parse(data=r.text, format="turtle")
    return g


def fetch_graph(graph_uri: str) -> Graph:
    r = requests.get(
        f"{BASE_URL}/store",
        params={"graph": graph_uri},
        headers={"Accept": "text/turtle"},
        timeout=30
    )
    r.raise_for_status()
    g = Graph()
    g.parse(data=r.text, format="turtle")
    return g


def upload_graph(graph_uri: str, turtle_str: str):
    r = requests.put(
        f"{BASE_URL}/store",
        params={"graph": graph_uri},
        headers={"Content-Type": "text/turtle"},
        data=turtle_str.encode()
    )
    r.raise_for_status()
    print(f"[Oxigraph] Uploaded to <{graph_uri}> — {r.status_code}")


def append_graph(graph_uri: str, turtle_str: str):
    r = requests.post(
        f"{BASE_URL}/store",
        params={"graph": graph_uri},
        headers={"Content-Type": "text/turtle"},
        data=turtle_str.encode()
    )
    r.raise_for_status()


def delete_graph(graph_uri: str):
    requests.delete(
        f"{BASE_URL}/store",
        params={"graph": graph_uri}
    ).raise_for_status()


def graph_exists(graph_uri: str) -> bool:
    return sparql_query(
        f"ASK {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}"
    ).get("boolean", False)


def count_triples(graph_uri: str) -> int:
    r = sparql_query(
        f"SELECT (COUNT(*) AS ?c) WHERE "
        f"{{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}"
    )
    return int(r["results"]["bindings"][0]["c"]["value"])