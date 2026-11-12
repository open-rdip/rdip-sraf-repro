#!/usr/bin/env python3
"""Pool several extractors into the canonical study graphs, reversibly.

Why
---
The canonical graphs were enriched on 2 Sep 2025 with Mistral-24B alone, and
section 7.1's invariance null rests on them. The obvious reviewer objection to
any null is that it is an artefact of measurement: a 24B open-weight extractor
missed the metadata, so of course the criteria look invariant.

Pooling answers that with an upper bound. Mistral + Grok + GPT-5 + Sonnet is
3.59x the distinct items of Mistral alone (7,779 against 2,164 over 95
studies). If 57.8 points stay invariant under that, no single better extractor
could have broken it. If invariance breaks, extraction depth drives the result,
which is a larger finding than the null.

Reversibility is the whole design
---------------------------------
`merge` is append-only and `map_extraction` mints random UUIDs, so pooled
triples cannot be subtracted out afterwards. There is no backup of these graphs
in git or as turtle. Pool without a snapshot and the Mistral-only baseline is
unrecoverable except by re-cloning 95 repositories, which would destroy the
very comparison this exists to make. Hence `pool` refuses to run without a
verified snapshot.

Order
-----
    python -m analysis.pool_extractors snapshot
    python -m analysis.pool_extractors verify  --study study001
    python -m analysis.pool_extractors pool    --snapshot backups/graphs_<ts>
    python -m analysis.pool_extractors restore --snapshot backups/graphs_<ts>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_pipeline.mapper import map_extraction, to_turtle          # noqa: E402
from triplestore_client import (append_graph, count_triples,       # noqa: E402
                                delete_graph, fetch_graph,
                                graph_exists, upload_graph)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_BASE = "https://w3id.org/rdip/graph"
EXTRACTIONS = os.path.join(ROOT, "data", "extractions")
MARK_DIR = os.path.join(ROOT, "validation", "pooled_done")

#: Full-corpus, uncontaminated. Mistral is already merged and is listed so the
#: marker file records the complete composition of the pooled graph.
#: Excluded on purpose: Gemini (ground truth came from that family), Opus
#: (12 of 95 studies, which would confound the gold tier with deeper
#: extraction, and ~$25 to complete at lower yield than Grok).
DEFAULT_POOL = ["grok-4-7", "gpt-5", "claude-sonnet-5-5"]
ALREADY_MERGED = ["redhatai-mistral-small-24b-instruct-2501-quantized-w8a8"]


def studies(slug: str) -> list[str]:
    return sorted(os.path.basename(p).split("__")[0]
                  for p in glob.glob(os.path.join(EXTRACTIONS, f"*__{slug}.json")))


def canonical(study: str) -> str:
    return f"{GRAPH_BASE}/{study}"


# ── snapshot / restore ──────────────────────────────────────────────────────

def cmd_snapshot(args) -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or os.path.join(ROOT, "backups", f"graphs_{ts}")
    os.makedirs(out, exist_ok=True)
    sids = studies(ALREADY_MERGED[0])
    print(f"snapshotting {len(sids)} canonical graphs -> {out}\n")
    man = {"created": ts, "graphs": {}}
    for sid in sids:
        uri = canonical(sid)
        if not graph_exists(uri):
            print(f"  {sid}: MISSING, skipped"); continue
        g = fetch_graph(uri)
        p = os.path.join(out, f"{sid}.ttl")
        g.serialize(destination=p, format="turtle")
        man["graphs"][sid] = {"triples": len(g), "bytes": os.path.getsize(p)}
        print(f"  {sid}: {len(g):>5} triples")
    got, want = len(man["graphs"]), len(sids)
    if got == 0:
        print(f"\nSNAPSHOT FAILED: {want} studies expected, 0 graphs found.")
        print("  Nothing was written, so nothing claims to be a backup.")
        print("  The canonical graphs are not in the store this client is "
              "pointed at. Check OXIGRAPH_URL, and note that the 2 Sep merge "
              "ran on the cluster, not the Mac.")
        return 2
    if got < want:
        print(f"\nSNAPSHOT INCOMPLETE: {got} of {want} graphs captured.")
        print("  Writing it as PARTIAL so it cannot be used for pooling.")
        man["partial"] = True
    man["expected"] = want
    json.dump(man, open(os.path.join(out, "MANIFEST.json"), "w"), indent=1)
    print(f"\nsnapshot: {got} of {want} graphs, "
          f"{sum(v['triples'] for v in man['graphs'].values())} triples")
    if man.get("partial"):
        print("  PARTIAL. Fix the store before pooling; pool will refuse this.")
        return 2
    print(f"  pool with:   python -m analysis.pool_extractors pool --snapshot {out}")
    return 0


def _check_snapshot(path: str) -> dict:
    man_p = os.path.join(path, "MANIFEST.json")
    if not os.path.isfile(man_p):
        sys.exit(f"no MANIFEST.json in {path}; that is not a snapshot")
    man = json.load(open(man_p))
    if not man.get("graphs"):
        sys.exit(f"{path} holds 0 graphs. An empty snapshot is not a backup, and "
                 f"pooling into graphs that do not exist would create them "
                 f"containing only the pooled models, destroying the Mistral "
                 f"baseline this exists to preserve.")
    if man.get("partial"):
        sys.exit(f"{path} is marked PARTIAL ({len(man['graphs'])} of "
                 f"{man.get('expected', '?')} graphs). Refusing to pool.")
    missing = [s for s in man["graphs"] if not os.path.isfile(os.path.join(path, f"{s}.ttl"))]
    if missing:
        sys.exit(f"snapshot incomplete, {len(missing)} turtle files missing: {missing[:5]}")
    exp = man.get("expected")
    if exp and len(man["graphs"]) < exp:
        sys.exit(f"{path} has {len(man['graphs'])} graphs but expected {exp}.")
    return man


def cmd_restore(args) -> int:
    man = _check_snapshot(args.snapshot)
    sids = [args.study] if args.study else sorted(man["graphs"])
    print(f"restoring {len(sids)} graph(s) from {args.snapshot}\n")
    for sid in sids:
        uri = canonical(sid)
        ttl = open(os.path.join(args.snapshot, f"{sid}.ttl"), encoding="utf-8").read()
        if not args.dry_run:
            delete_graph(uri)
            upload_graph(uri, ttl)
            now = count_triples(uri)
        else:
            now = None
        want = man["graphs"][sid]["triples"]
        ok = "ok" if (now is None or now == want) else f"MISMATCH want {want} got {now}"
        print(f"  {sid}: {want} triples  {ok}")
        # pooling must be re-doable after a restore
        for f in glob.glob(os.path.join(MARK_DIR, f"{sid}__*.pooled")):
            if not args.dry_run:
                os.remove(f)
    return 0


# ── pooling ─────────────────────────────────────────────────────────────────

def _merge_one(study: str, slug: str, dry_run: bool) -> tuple[str, int]:
    p = os.path.join(EXTRACTIONS, f"{study}__{slug}.json")
    if not os.path.isfile(p):
        return "no-extraction", 0
    mark = os.path.join(MARK_DIR, f"{study}__{slug}.pooled")
    if os.path.isfile(mark):
        return "skip", 0
    doc = json.load(open(p))
    g = map_extraction(study, doc.get("metadata", doc))
    if dry_run:
        return "would-merge", len(g)
    append_graph(canonical(study), to_turtle(g))
    total = count_triples(canonical(study))
    os.makedirs(MARK_DIR, exist_ok=True)
    json.dump({"slug": slug, "added": len(g), "total": total}, open(mark, "w"))
    return "merged", len(g)


def cmd_pool(args) -> int:
    if not args.dry_run:
        _check_snapshot(args.snapshot)
    pool = args.models.split(",") if args.models else DEFAULT_POOL
    sids = [args.study] if args.study else studies(ALREADY_MERGED[0])
    print(f"pooling {len(pool)} model(s) into {len(sids)} graph(s)"
          f"{'  (dry run)' if args.dry_run else ''}")
    print(f"  already in the graphs: {', '.join(ALREADY_MERGED)}")
    print(f"  adding: {', '.join(pool)}\n")
    tally = {}
    for slug in pool:
        added = n = 0
        for sid in sids:
            status, k = _merge_one(sid, slug, args.dry_run)
            if status in ("merged", "would-merge"):
                added += k; n += 1
            elif status == "no-extraction":
                print(f"  {sid}: no extraction for {slug}")
        tally[slug] = (n, added)
        print(f"  {slug:<26} {n:>3} studies, {added:>6} triples")
    print("\n  total triples added:", sum(v[1] for v in tally.values()))
    if not args.dry_run:
        print("\n  next:  python -m build_harness.rescore")
        print("         python -m analysis.predictor_analysis")
    return 0


# ── verification on one study ───────────────────────────────────────────────

def cmd_verify(args) -> int:
    """Pool one study, report the before/after, then put it back.

    Guards against the failure I would otherwise create: FAIR-R criteria use
    sh:minCount 1, so presence rather than counts, and pooling should not move
    a score mechanically. If a criterion does move purely from duplicate
    entities, the whole exercise measures my merge rather than the corpus.
    """
    sid = args.study
    uri = canonical(sid)
    # `before` is whatever is in the store RIGHT NOW. If this study has already
    # been pooled, that is the pooled graph, and --restore would faithfully
    # restore the pooled state while reporting success. Observed 12 Nov: the
    # second invocation "restored" study001 to 759 triples instead of 251.
    # verify is a single atomic call, not two.
    done = glob.glob(os.path.join(MARK_DIR, f"{sid}__*.pooled"))
    if done:
        models = ", ".join(os.path.basename(f).split("__")[1][:-7] for f in done)
        sys.exit(
            f"{sid} is already pooled ({models}).\n"
            f"  'before' would be the pooled graph, so --restore here would be a\n"
            f"  no-op that reports success. Restore from the snapshot instead:\n"
            f"    python -m analysis.pool_extractors restore "
            f"--snapshot <dir> --study {sid}")
    before_g = fetch_graph(uri)
    before_ttl = before_g.serialize(format="turtle")
    print(f"  {sid}: {len(before_g)} triples before\n")
    pool = args.models.split(",") if args.models else DEFAULT_POOL
    for slug in pool:
        status, k = _merge_one(sid, slug, dry_run=False)
        print(f"    {slug:<26} {status}, +{k}")
    after = count_triples(uri)
    print(f"\n  {sid}: {len(before_g)} -> {after} triples "
          f"({after / max(len(before_g), 1):.2f}x)")
    print("\n  Now score this study both ways before trusting the full run:")
    print(f"    python -m build_harness.rescore --study {sid}")
    if args.restore:
        delete_graph(uri)
        upload_graph(uri, before_ttl)
        for f in glob.glob(os.path.join(MARK_DIR, f"{sid}__*.pooled")):
            os.remove(f)
        print(f"\n  restored {sid} to {count_triples(uri)} triples, markers cleared")
    else:
        print(f"\n  NOT restored. Re-run with --restore, or restore from a snapshot.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="back up every canonical graph to turtle")
    s.add_argument("--out"); s.set_defaults(fn=cmd_snapshot)

    s = sub.add_parser("verify", help="pool one study and report the delta")
    s.add_argument("--study", required=True)
    s.add_argument("--models")
    s.add_argument("--restore", action="store_true", help="put the study back afterwards")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("pool", help="pool the models into every canonical graph")
    s.add_argument("--snapshot", required=True, help="a verified snapshot directory")
    s.add_argument("--models"); s.add_argument("--study")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_pool)

    s = sub.add_parser("restore", help="restore graphs from a snapshot")
    s.add_argument("--snapshot", required=True)
    s.add_argument("--study"); s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_restore)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
