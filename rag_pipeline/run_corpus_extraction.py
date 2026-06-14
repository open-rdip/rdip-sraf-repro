"""Run Phase II extraction over the Dataset B corpus with the configured backend.

Loops validation/repo_list.csv, downloads each paper PDF, runs the RAG pipeline
(retrieve -> LLM extract -> map -> append RDIP triples to the study graph).
Resumable: a marker file per study lets a re-submission pick up where it left off.

Driven by env (set by cluster/extract_corpus.sbatch):
  LLM_BACKEND=vllm  LLM_MODEL=<repo>  VLLM_SERVER_URL=http://127.0.0.1:8000
  OXIGRAPH_HOST/PORT  ·  SRAF_LIMIT (0=all)  ·  SRAF_FORCE=1 (re-extract)
"""
from __future__ import annotations
import csv
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from rag_pipeline.pipeline import run          # noqa: E402
from config import LLM_BACKEND, LLM_MODEL      # noqa: E402

REPO_LIST = REPO_ROOT / "validation" / "repo_list.csv"
MARK_DIR = REPO_ROOT / "validation" / "extraction_done"


def main():
    if not REPO_LIST.exists():
        print(f"Missing {REPO_LIST}")
        return
    MARK_DIR.mkdir(parents=True, exist_ok=True)
    limit = int(os.getenv("SRAF_LIMIT", "0"))
    force = os.getenv("SRAF_FORCE") == "1"
    print(f"Corpus extraction — backend={LLM_BACKEND} model={LLM_MODEL}")

    rows = list(csv.DictReader(open(REPO_LIST)))
    processed = 0
    for r in rows:
        sid = r.get("study_id")
        pdf = (r.get("paper_url_pdf") or r.get("paper_url") or "").strip()
        if not sid:
            continue
        mark = MARK_DIR / f"{sid}.done"
        if mark.exists() and not force:
            print(f"  {sid}: already extracted — skip")
            continue
        if not pdf.startswith("http"):
            print(f"  {sid}: no usable PDF url — skip")
            continue

        processed += 1
        if limit and processed > limit:
            print(f"  reached SRAF_LIMIT={limit}")
            break
        try:
            res = run(study_id=sid, pdf_url=pdf)
            mark.write_text(json.dumps(res))
            print(f"  {sid}: +{res.get('triples_added', 0)} triples "
                  f"(seeds={res.get('seeds_found', 0)}, params={res.get('params_found', 0)})")
        except Exception as e:  # noqa: BLE001 — one bad paper must not stop the run
            print(f"  {sid}: extraction FAILED — {e}")

    print(f"\nDone. Processed {processed} papers this submission.")


if __name__ == "__main__":
    main()
