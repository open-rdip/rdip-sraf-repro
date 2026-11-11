#!/usr/bin/env python3
"""Recompute the grounded verification over existing output, in place.

Why this exists
---------------
Verification rules changed after output had already been written. The
whitespace-insensitive span match (`span_loose`) was added once the first
smoke run showed that most apparent span failures were PDF extraction
dropping word boundaries, not models misquoting. Re-running the models to
pick up a scoring change would be absurd: the extractions are fine, only the
checks moved.

Files written after the change carry their `passages`, so they re-score with
no I/O at all. Files written before it do not, so their passages are
re-retrieved. Retrieval is deterministic given the cached embeddings and the
fixed query set, and costs no model calls.

Usage:
    python -m analysis.rescore_grounded              # re-score everything
    python -m analysis.rescore_grounded --dry-run    # report, change nothing
    python -m analysis.rescore_grounded --slug grok-4-7
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_pipeline.grounded import OUT_DIR, summarise, verify  # noqa: E402


def _passages_for(study_id: str) -> list[str] | None:
    """Re-retrieve a legacy file's passages. Deterministic, no model calls."""
    try:
        import csv
        from rag_pipeline.grounded import _passages, _rows_for
        for tier in ("gold", "silver"):
            for row in _rows_for(tier):
                sid = row.get("study_id") or row.get("id")
                if sid != study_id:
                    continue
                pdf = row.get("paper_url_pdf") or row.get("pdf_url") or ""
                if not pdf:
                    return None
                return _passages(study_id, pdf)
    except Exception as exc:                      # noqa: BLE001
        print(f"      re-retrieval failed: {exc}")
    return None


def rescore(path: str, dry_run: bool = False) -> dict:
    d = json.load(open(path, encoding="utf-8"))
    passages = d.get("passages")
    source = "stored"
    if not passages:
        passages = _passages_for(d["study_id"])
        source = "re-retrieved"
        if not passages:
            return {"path": path, "status": "skipped: no passages"}

    before = d["summary"]["total"]
    records = []
    for blk in d.get("raw") or []:
        i = blk.get("passage_index", 0)
        if i >= len(passages):
            return {"path": path, "status": f"skipped: passage_index {i} out of range"}
        records += verify(blk.get("extraction") or {}, passages[i])

    if len(records) != len(d["records"]):
        return {"path": path,
                "status": f"skipped: {len(records)} records vs {len(d['records'])} stored"}

    after = summarise(records)["total"]
    if not dry_run:
        d["records"] = records
        d["summary"] = summarise(records)
        d["passages"] = passages
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=1)
        os.replace(tmp, path)
    return {"path": path, "status": "ok", "source": source,
            "n": after.get("n", 0),
            "span_before": before.get("span_found", 0),
            "span_after": after.get("span_found", 0),
            "span_any": after.get("span_any", 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="", help="restrict to one model slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pat = f"*__{args.slug}.json" if args.slug else "*.json"
    files = sorted(glob.glob(os.path.join(OUT_DIR, pat)))
    print(f"re-scoring {len(files)} file(s){'  (dry run)' if args.dry_run else ''}\n")

    agg = {}
    for f in files:
        r = rescore(f, dry_run=args.dry_run)
        if r["status"] != "ok":
            print(f"  {os.path.basename(f):<60} {r['status']}")
            continue
        slug = os.path.basename(f).split("__")[1].rsplit(".", 1)[0]
        a = agg.setdefault(slug, {"n": 0, "strict": 0, "any": 0, "src": set()})
        a["n"] += r["n"]; a["strict"] += r["span_after"]; a["any"] += r["span_any"]
        a["src"].add(r["source"])

    print(f"  {'model':<52}{'items':>7}{'strict':>8}{'+ws':>8}")
    for slug, a in sorted(agg.items()):
        n = a["n"] or 1
        print(f"  {slug:<52}{a['n']:>7}{100*a['strict']/n:>7.0f}%{100*a['any']/n:>7.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
