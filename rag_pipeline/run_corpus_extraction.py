"""Run Phase II extraction over the Dataset B corpus — one or several models.

Loops validation/repo_list.csv, downloads each paper PDF, runs the RAG pipeline
(retrieve -> LLM extract -> map -> append RDIP triples) for EACH requested model.
Each model writes to its own model-scoped graph + extraction JSON, so the models
stay comparable for the RQ3 gold-standard evaluation. Resumable: a marker file
per (study, model) lets a re-submission pick up where it left off.

Driven by env (set by cluster/extract_corpus.sbatch):
  LLM_BACKEND=vllm  LLM_MODEL=<repo>  VLLM_SERVER_URL=http://127.0.0.1:8000
  OXIGRAPH_HOST/PORT  ·  SRAF_LIMIT (0=all)  ·  SRAF_FORCE=1 (re-extract)
  SRAF_MODELS  optional: comma-separated "backend:model" specs to run several
               models in one submission, e.g.
               "vllm:Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8,google:gemini-1.5-pro".
               If unset, falls back to the single configured LLM_BACKEND/LLM_MODEL.
"""
from __future__ import annotations
import csv
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from rag_pipeline.pipeline import run, model_slug   # noqa: E402
from config import LLM_BACKEND, LLM_MODEL           # noqa: E402

REPO_LIST = REPO_ROOT / "validation" / "repo_list.csv"
MARK_DIR = REPO_ROOT / "validation" / "extraction_done"


def parse_models() -> list[tuple[str, str]]:
    """Resolve the (backend, model) specs to run from SRAF_MODELS, else the
    single configured backend/model."""
    spec = os.getenv("SRAF_MODELS", "").strip()
    if not spec:
        return [(LLM_BACKEND, LLM_MODEL)]
    out: list[tuple[str, str]] = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        backend, _, model = item.partition(":")
        out.append((backend.strip(), model.strip()))
    return out


def main():
    if not REPO_LIST.exists():
        print(f"Missing {REPO_LIST}")
        return
    MARK_DIR.mkdir(parents=True, exist_ok=True)
    limit = int(os.getenv("SRAF_LIMIT", "0"))
    force = os.getenv("SRAF_FORCE") == "1"
    models = parse_models()
    print(f"Corpus extraction — {len(models)} model(s): "
          + ", ".join(f"{b}:{m}" for b, m in models))

    rows = list(csv.DictReader(open(REPO_LIST)))
    processed = 0
    for backend, model in models:
        slug = model_slug(model)
        print(f"\n=== model {backend}:{model} (slug={slug}) ===")
        for r in rows:
            sid = r.get("study_id")
            pdf = (r.get("paper_url_pdf") or r.get("paper_url") or "").strip()
            if not sid:
                continue
            mark = MARK_DIR / f"{sid}__{slug}.done"
            if mark.exists() and not force:
                print(f"  {sid}: already extracted ({slug}) — skip")
                continue
            if not pdf.startswith("http"):
                print(f"  {sid}: no usable PDF url — skip")
                continue

            processed += 1
            if limit and processed > limit:
                print(f"  reached SRAF_LIMIT={limit}")
                break
            try:
                res = run(study_id=sid, pdf_url=pdf, backend=backend, model=model)
                mark.write_text(json.dumps(res))
                print(f"  {sid}: +{res.get('triples_added', 0)} triples "
                      f"(seeds={res.get('seeds_found', 0)}, "
                      f"params={res.get('params_found', 0)}, "
                      f"evals={res.get('evals_found', 0)})")
            except Exception as e:  # noqa: BLE001 — one bad paper must not stop the run
                print(f"  {sid}: extraction FAILED — {e}")

    print(f"\nDone. Processed {processed} (study × model) runs this submission.")


if __name__ == "__main__":
    main()
