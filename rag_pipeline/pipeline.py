# rag_pipeline/pipeline.py
"""
Full Phase II pipeline: PDF → chunks → embeddings → LLM extraction
→ RDIP triples → Oxigraph (appended to existing Phase I graph).
"""

import os
import sys
import requests
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from triplestore_client import append_graph, count_triples, graph_exists
from rag_pipeline.chunker   import load_paper
from rag_pipeline.embedder  import EmbeddingStore
from rag_pipeline.extractor import extract_metadata, merge_extractions
from rag_pipeline.mapper    import map_extraction, to_turtle

GRAPH_BASE = "https://w3id.org/rdip/graph"

# Queries designed to surface reproducibility-critical passages
RETRIEVAL_QUERIES = [
    "random seed stochastic reproducibility initialization numpy torch",
    "GPU hardware CUDA device A100 V100 RTX compute",
    "software framework version PyTorch TensorFlow Python library",
    "learning rate batch size optimizer hyperparameter training",
    "dataset split training validation test benchmark evaluation",
    "hardware server CPU memory compute infrastructure",
]


def download_pdf(pdf_url: str, study_id: str) -> str:
    """
    Download a paper PDF to the local data/papers directory.
    Returns the local file path. Skips download if already present.
    """
    papers_dir = Path(__file__).parent.parent / "data" / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)

    dest = papers_dir / f"{study_id}.pdf"
    if dest.exists():
        print(f"[Pipeline] PDF already downloaded: {dest.name}")
        return str(dest)

    print(f"[Pipeline] Downloading PDF for {study_id} ...")
    r = requests.get(pdf_url, timeout=30)
    r.raise_for_status()

    with open(dest, "wb") as f:
        f.write(r.content)

    print(f"[Pipeline] Saved to {dest}")
    return str(dest)


def run(study_id: str,
        pdf_path: str = None,
        pdf_url: str  = None,
        rebuild_index: bool = False) -> dict:
    """
    Run the full Phase II pipeline for one study.

    Args:
        study_id:      matches the Phase I study ID
        pdf_path:      local path to the PDF (use this OR pdf_url)
        pdf_url:       URL to download the PDF from
        rebuild_index: force re-embedding even if index exists

    Returns:
        summary dict with extraction statistics
    """
    graph_uri = f"{GRAPH_BASE}/{study_id}"

    # ── Step 1: Get PDF ───────────────────────────────────────────────────────
    if pdf_path is None and pdf_url is None:
        raise ValueError("Provide either pdf_path or pdf_url")

    if pdf_path is None:
        pdf_path = download_pdf(pdf_url, study_id)

    print(f"\n[Pipeline] Study:   {study_id}")
    print(f"[Pipeline] PDF:     {pdf_path}")
    print(f"[Pipeline] Graph:   {graph_uri}")

    # ── Step 2: Chunk the PDF ─────────────────────────────────────────────────
    chunks = load_paper(pdf_path, methods_only=True)
    if not chunks:
        print("[Pipeline] WARNING: No text extracted from PDF")
        return {"study_id": study_id, "status": "no_text", "triples_added": 0}

    # ── Step 3: Build / load embedding index ─────────────────────────────────
    store = EmbeddingStore(study_id)
    if rebuild_index or not store.is_built():
        store.build(chunks)
    else:
        print(f"[Pipeline] Using cached embeddings for {study_id}")
        store.load()

    # ── Step 4: Retrieve relevant passages and extract ────────────────────────
    all_extractions = []
    seen_passages   = set()

    for query in RETRIEVAL_QUERIES:
        passages = store.retrieve(query, top_k=3)
        for passage in passages:
            # Avoid sending identical passages twice
            key = passage[:100]
            if key in seen_passages:
                continue
            seen_passages.add(key)

            extracted = extract_metadata(passage)
            if extracted:
                all_extractions.append(extracted)

    # ── Step 5: Merge extractions ─────────────────────────────────────────────
    merged = merge_extractions(all_extractions)

    print(f"\n[Pipeline] Extraction summary for {study_id}:")
    print(f"  Dependencies:    {len(merged['dependencies'])}")
    print(f"  Random seeds:    {len(merged['random_seeds'])}")
    print(f"  Hyperparameters: {len(merged['hyperparameters'])}")
    print(f"  Hardware:        {merged['hardware']}")
    print(f"  Datasets:        {len(merged['datasets'])}")
    print(f"  Methods:         {len(merged['methods'])}")

    # ── Step 6: Map to RDIP and append to graph ───────────────────────────────
    g      = map_extraction(study_id, merged)
    turtle = to_turtle(g)

    append_graph(graph_uri, turtle)
    total = count_triples(graph_uri)

    print(f"\n[Pipeline] Appended {len(g)} triples → "
          f"graph now has {total} total triples")

    return {
        "study_id":       study_id,
        "status":         "ok",
        "chunks":         len(chunks),
        "extractions":    len(all_extractions),
        "seeds_found":    len(merged["random_seeds"]),
        "params_found":   len(merged["hyperparameters"]),
        "triples_added":  len(g),
        "total_triples":  total,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RDIP RAG Pipeline — Phase II"
    )
    parser.add_argument("--study-id",  required=True)
    parser.add_argument("--pdf-path",  default=None,
                        help="Local path to PDF")
    parser.add_argument("--pdf-url",   default=None,
                        help="URL to download PDF from")
    parser.add_argument("--rebuild",   action="store_true",
                        help="Force rebuild of embedding index")
    args = parser.parse_args()

    result = run(
        study_id      = args.study_id,
        pdf_path      = args.pdf_path,
        pdf_url       = args.pdf_url,
        rebuild_index = args.rebuild,
    )
    print(f"\n[Pipeline] Result: {result}")


if __name__ == "__main__":
    main()
