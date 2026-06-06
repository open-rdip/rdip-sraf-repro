"""
SRAF central configuration.

Every module reads from here, not from os.getenv directly.
On the Mac, defaults work out of the box with docker compose.
On the cluster, override via Slurm env vars or .env file.

Run `python config.py` to print the effective configuration.
"""
from __future__ import annotations
import os
from pathlib import Path


# -----------------------------------------------------------------------------
# Paths — repo root and key subdirectories
# -----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("SRAF_DATA_DIR", REPO_ROOT / "data"))
OUTPUT_DIR = Path(os.getenv("SRAF_OUTPUT_DIR", REPO_ROOT / "validation" / "results"))
LOG_DIR = Path(os.getenv("SRAF_LOG_DIR", REPO_ROOT / "logs"))
CORPUS_DIR = Path(os.getenv("SRAF_CORPUS_DIR", REPO_ROOT / "test_repos"))

for d in (DATA_DIR, OUTPUT_DIR, LOG_DIR, CORPUS_DIR):
    d.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# Triplestore — Oxigraph
# -----------------------------------------------------------------------------
OXIGRAPH_HOST = os.getenv("OXIGRAPH_HOST", "localhost")
OXIGRAPH_PORT = int(os.getenv("OXIGRAPH_PORT", "7878"))
OXIGRAPH_URL = f"http://{OXIGRAPH_HOST}:{OXIGRAPH_PORT}"
OXIGRAPH_QUERY_URL = f"{OXIGRAPH_URL}/query"
OXIGRAPH_UPDATE_URL = f"{OXIGRAPH_URL}/update"
OXIGRAPH_STORE_URL = f"{OXIGRAPH_URL}/store"

# Legacy alias — for any code that imports BASE_URL directly
BASE_URL = OXIGRAPH_URL


# -----------------------------------------------------------------------------
# RDIP ontology
# -----------------------------------------------------------------------------
RDIP_NAMESPACE = os.getenv("RDIP_NAMESPACE", "https://w3id.org/rdip/")
RDIP_GRAPH_BASE = os.getenv("RDIP_GRAPH_BASE", "https://w3id.org/rdip/graph/")


# -----------------------------------------------------------------------------
# LLM extractor — runtime selection
# -----------------------------------------------------------------------------
# One of: "openai", "llamacpp", "vllm"
LLM_BACKEND = os.getenv("LLM_BACKEND", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))

# Backend-specific
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLAMACPP_SERVER_URL = os.getenv("LLAMACPP_SERVER_URL", "http://localhost:8080")
VLLM_SERVER_URL = os.getenv("VLLM_SERVER_URL", "http://localhost:8000")


# -----------------------------------------------------------------------------
# Embeddings
# -----------------------------------------------------------------------------
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")


# -----------------------------------------------------------------------------
# Build harness (used later in Bucket C)
# -----------------------------------------------------------------------------
BUILD_SCRATCH_DIR = Path(os.getenv("SRAF_SCRATCH_DIR", "/tmp/sraf_scratch"))
BUILD_TIMEOUT_SECONDS = int(os.getenv("SRAF_BUILD_TIMEOUT", "1800"))
APPTAINER_BIN = os.getenv("APPTAINER_BIN", "apptainer")


def describe() -> str:
    """Print effective config — useful for debugging container env vars."""
    items = [
        ("REPO_ROOT", REPO_ROOT),
        ("OXIGRAPH_URL", OXIGRAPH_URL),
        ("LLM_BACKEND", LLM_BACKEND),
        ("LLM_MODEL", LLM_MODEL),
        ("EMBEDDING_MODEL", EMBEDDING_MODEL),
        ("DATA_DIR", DATA_DIR),
        ("OUTPUT_DIR", OUTPUT_DIR),
        ("LOG_DIR", LOG_DIR),
        ("CORPUS_DIR", CORPUS_DIR),
    ]
    return "\n".join(f"  {k:20s} {v}" for k, v in items)


if __name__ == "__main__":
    print("SRAF configuration:")
    print(describe())
