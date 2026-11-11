"""Retrieval inputs shared by the pipeline and the grounded pilot.

Why this module exists
----------------------
`RETRIEVAL_QUERIES` and `download_pdf` need nothing but `requests` and a
path. They lived in `rag_pipeline.pipeline`, which imports the triplestore
client at module load, so anything wanting the query set or a PDF also had to
have a working SPARQL stack. That is the wrong shape for two callers in
particular: the grounded pilot, which never writes a triple, and
`analysis.rescore_grounded`, which only re-reads JSON and recomputes string
comparisons yet failed outright with ModuleNotFoundError: SPARQLWrapper.

Defining them here and re-exporting from `pipeline` keeps one definition, so
the two cannot drift, while letting the verification path import them with no
graph store present.
"""
from __future__ import annotations

from pathlib import Path

import requests

#: Queries designed to surface reproducibility-critical passages. Changing
#: these changes which passages every extractor sees, so any edit invalidates
#: comparison with existing output.
RETRIEVAL_QUERIES = [
    "random seed stochastic reproducibility initialization numpy torch",
    "GPU hardware CUDA device A100 V100 RTX compute",
    "software framework version PyTorch TensorFlow Python library",
    "learning rate batch size optimizer hyperparameter training",
    "dataset split training validation test benchmark evaluation",
    "hardware server CPU memory compute infrastructure",
]


def download_pdf(pdf_url: str, study_id: str) -> str:
    """Download a paper PDF to data/papers. Returns the local path.

    Skips the download when the file is already present, which is what makes
    re-scoring free on a machine that has already run the corpus.
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
