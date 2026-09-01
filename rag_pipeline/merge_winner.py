#!/usr/bin/env python3
"""
Merge the winning model's extractions into the canonical study graphs (RQ4 prep).

After RQ3 selects the best extractor (Mistral-24B), its per-study extraction was
written to a *model-scoped* graph (…/graph/<study>/ext/<slug>) and saved as
data/extractions/<study>__<slug>.json. To give the FAIR-R scorer (which reads the
canonical graph …/graph/<study>) the paper-level metadata, we map each saved
extraction to RDIP triples and append it to the canonical graph.

Non-destructive (append only); resumable via a marker per study. Run on the
cluster where Oxigraph + the extraction JSONs live:

  OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT=7878 \
    ~/envs/sraf/bin/python -m rag_pipeline.merge_winner \
        --model redhatai-mistral-small-24b-instruct-2501-quantized-w8a8

Then: build_harness.rescore  →  analysis.predictor_analysis (RQ1, RQ4).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from triplestore_client import append_graph, count_triples
from rag_pipeline.mapper import map_extraction, to_turtle

GRAPH_BASE = "https://w3id.org/rdip/graph"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _study_of(path: str, slug: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    return base[: -(len(slug) + 2)] if base.endswith(f"__{slug}") else base


def merge(model_slug: str, extractions_dir: str, mark_dir: str,
          force: bool = False, dry_run: bool = False):
    os.makedirs(mark_dir, exist_ok=True)
    results = []
    for path in sorted(glob.glob(os.path.join(extractions_dir, f"*__{model_slug}.json"))):
        doc = json.load(open(path))
        study = doc.get("study_id") or _study_of(path, model_slug)
        mark = os.path.join(mark_dir, f"{study}.merged")
        if os.path.exists(mark) and not force:
            results.append((study, "skip", 0)); continue
        merged = doc.get("metadata", doc)
        g = map_extraction(study, merged)
        canonical = f"{GRAPH_BASE}/{study}"
        if not dry_run:
            append_graph(canonical, to_turtle(g))
            total = count_triples(canonical)
            open(mark, "w").write(json.dumps({"triples_added": len(g), "total": total}))
        else:
            total = None
        results.append((study, "merged", len(g)))
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="winning model slug")
    ap.add_argument("--extractions", default=os.path.join(ROOT, "data", "extractions"))
    ap.add_argument("--mark-dir", default=os.path.join(ROOT, "validation", "merged_done"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    res = merge(args.model, args.extractions, args.mark_dir, args.force, args.dry_run)
    merged = sum(1 for _, s, _ in res if s == "merged")
    added = sum(n for _, s, n in res if s == "merged")
    for study, status, n in res:
        print(f"  {study:10s} {status:7s} +{n} triples")
    print(f"\nMerged {merged} studies (+{added} triples) into canonical graphs"
          + (" [DRY RUN]" if args.dry_run else ""))
    print("Next: build_harness.rescore  →  analysis.predictor_analysis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
