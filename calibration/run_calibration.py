#!/usr/bin/env python3
"""
Calibration harness for the FAIR-R rubric — construct validity.

Implements check (1) of the calibration plan in
docs/fair_r_scoring_rubric.md §5: does the rubric rank artifacts that SHOULD
score high (ACM "Results Reproduced" / "Artifacts Evaluated — Reusable" badges,
ReScience-C / ML Reproducibility Challenge successful reproductions; repos with
a licence, pinned environment, and seeds) ABOVE artifacts that should score low
(no licence, no seeds, no pinned environment)?

It scores every reference entry that is present in the Knowledge Graph and
reports:
  • band means / ranges,
  • pairwise rank concordance (fraction of cross-band pairs ordered as expected),
  • Spearman rho and a Mann-Whitney U test (if scipy is available).

Entries not yet lifted into the KG are skipped with a warning, so the harness
can be run incrementally as reference artifacts are added.

  python calibration/run_calibration.py [--set calibration/reference_set.yaml]
                                        [--json out.json]

Companion check (2), the F-UJI benchmark, is documented in
calibration/fuji_benchmark.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ordinal value of each expected band (higher = should score higher).
BAND_ORDINAL = {"low": 0, "mid": 1, "high": 2}


# ── Pure metrics (no KG, no scipy — unit tested) ──────────────────────────────

def pairwise_concordance(items: list[tuple[int, float]]) -> float:
    """Fraction of cross-band pairs whose score ordering matches the expected
    band ordering.

    `items` is a list of (expected_ordinal, computed_score). Pairs within the
    same band are ignored. Returns 1.0 for a perfectly consistent ranking,
    0.0 for a perfectly inverted one, 0.5 for chance; NaN if there are no
    cross-band pairs. Ties in score count as half-concordant.
    """
    pairs = concordant = 0.0
    for (ei, si), (ej, sj) in combinations(items, 2):
        if ei == ej:
            continue
        pairs += 1
        direction = (ei - ej) * (si - sj)
        if direction > 0:
            concordant += 1
        elif direction == 0:       # score tie across different bands
            concordant += 0.5
    return concordant / pairs if pairs else float("nan")


def band_summary(items: list[tuple[int, float]]) -> dict:
    """Per-band count / mean / min / max of computed scores."""
    inv = {v: k for k, v in BAND_ORDINAL.items()}
    out: dict[str, dict] = {}
    for ordv in sorted({o for o, _ in items}):
        scores = [s for o, s in items if o == ordv]
        out[inv[ordv]] = {
            "n": len(scores),
            "mean": round(sum(scores) / len(scores), 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
        }
    return out


def separation(items: list[tuple[int, float]]) -> float | None:
    """min(high-band scores) − max(low-band scores). Positive ⇒ the bands are
    cleanly separated by the rubric. None if either band is missing."""
    highs = [s for o, s in items if o == BAND_ORDINAL["high"]]
    lows = [s for o, s in items if o == BAND_ORDINAL["low"]]
    if not highs or not lows:
        return None
    return round(min(highs) - max(lows), 2)


# ── Optional statistical tests (scipy) ────────────────────────────────────────

def stats_tests(items: list[tuple[int, float]]) -> dict:
    try:
        from scipy import stats
    except ImportError:
        return {"available": False}
    ords = [o for o, _ in items]
    scrs = [s for _, s in items]
    res: dict = {"available": True}
    if len(set(ords)) > 1:
        rho, p = stats.spearmanr(ords, scrs)
        res["spearman_rho"] = round(float(rho), 3)
        res["spearman_p"] = round(float(p), 4)
    highs = [s for o, s in items if o == BAND_ORDINAL["high"]]
    lows = [s for o, s in items if o == BAND_ORDINAL["low"]]
    if highs and lows:
        u, p = stats.mannwhitneyu(highs, lows, alternative="greater")
        res["mannwhitney_u"] = round(float(u), 2)
        res["mannwhitney_p"] = round(float(p), 4)
    return res


# ── Reference-set loading + scoring ───────────────────────────────────────────

def load_reference_set(path: str) -> list[dict]:
    import yaml  # lazy — only needed at runtime
    with open(path) as fh:
        doc = yaml.safe_load(fh)
    entries: list[dict] = []
    for section in ("external", "internal"):
        for e in (doc.get(section) or []):
            e = dict(e)
            e["section"] = section
            entries.append(e)
    return entries


def score_reference_set(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Score every entry whose study_id is in the KG. Returns (scored, skipped)."""
    from dashboard.fair_r_scorer import compute_fair_r
    from triplestore_client import graph_exists

    scored, skipped = [], []
    for e in entries:
        sid = e["study_id"]
        graph_uri = f"https://w3id.org/rdip/graph/{sid}"
        try:
            present = graph_exists(graph_uri)
        except Exception as exc:                       # KG offline, etc.
            skipped.append({**e, "reason": f"KG error: {exc}"})
            continue
        if not present:
            skipped.append({**e, "reason": "not in KG"})
            continue
        r = compute_fair_r(sid)
        scored.append({
            "study_id": sid,
            "band": e["band"],
            "ordinal": BAND_ORDINAL[e["band"]],
            "score": r["total_score"],
            "tier": r["tier"],
            "section": e["section"],
            "note": e.get("note", ""),
        })
    return scored, skipped


def build_report(scored: list[dict], skipped: list[dict]) -> dict:
    items = [(s["ordinal"], s["score"]) for s in scored]
    report = {
        "n_scored": len(scored),
        "n_skipped": len(skipped),
        "bands": band_summary(items) if items else {},
        "pairwise_concordance": (
            round(pairwise_concordance(items), 3) if len(items) > 1 else None
        ),
        "high_low_separation": separation(items),
        "statistics": stats_tests(items) if items else {"available": False},
        "scored": sorted(scored, key=lambda s: -s["score"]),
        "skipped": skipped,
    }
    return report


def print_report(rep: dict) -> None:
    print(f"\n=== FAIR-R calibration ({rep['n_scored']} scored, "
          f"{rep['n_skipped']} skipped) ===")
    for band, st in rep["bands"].items():
        print(f"  {band:5s}: n={st['n']:2d}  mean={st['mean']:5.1f}  "
              f"range=[{st['min']:.1f}, {st['max']:.1f}]")
    pc = rep["pairwise_concordance"]
    print(f"\n  pairwise rank concordance : {pc if pc is not None else 'n/a'} "
          f"(1.0 = expected ranking always holds)")
    sep = rep["high_low_separation"]
    print(f"  high−low separation       : {sep if sep is not None else 'n/a'} "
          f"(positive ⇒ bands cleanly separated)")
    stt = rep["statistics"]
    if stt.get("available"):
        if "spearman_rho" in stt:
            print(f"  Spearman rho (band,score) : {stt['spearman_rho']} "
                  f"(p={stt['spearman_p']})")
        if "mannwhitney_p" in stt:
            print(f"  Mann-Whitney high>low     : U={stt['mannwhitney_u']} "
                  f"(p={stt['mannwhitney_p']})")
    else:
        print("  (install scipy for Spearman / Mann-Whitney tests)")
    print("\n  ranked:")
    for s in rep["scored"]:
        print(f"    {s['score']:5.1f}  {s['tier']:9s}  [{s['band']:4s}]  "
              f"{s['study_id']}")
    if rep["skipped"]:
        print("\n  skipped:")
        for s in rep["skipped"]:
            print(f"    {s['study_id']:24s}  — {s['reason']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--set", default=os.path.join(here, "reference_set.yaml"))
    ap.add_argument("--json", default=None, help="also write the report as JSON")
    args = ap.parse_args()

    entries = load_reference_set(args.set)
    scored, skipped = score_reference_set(entries)
    report = build_report(scored, skipped)
    print_report(report)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(report, fh, indent=2)
        print(f"\n[calibration] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
