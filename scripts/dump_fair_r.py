"""Dump the full per-criterion FAIR-R breakdown for one or more studies.

Used to populate the paper's worked-example table (Table 4) with real,
criterion-level values for both the typical repository and the reference
exemplar, instead of aggregated per-dimension subtotals.

Prereq: Oxigraph must be serving the triplestore that holds each study's
RDIP graph, e.g.
    ~/bin/oxigraph serve --location ~/triplestore --bind 127.0.0.1:7878 &
    export OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT=7878

Run:
    ~/envs/sraf/bin/python -m scripts.dump_fair_r study042 ref005
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dashboard.fair_r_scorer import compute_fair_r  # noqa: E402


def grade(points: float, mx: float) -> float:
    return round(points / mx, 2) if mx else 0.0


def dump(study_id: str) -> None:
    r = compute_fair_r(study_id)
    print("\n" + "=" * 68)
    print(f"{study_id}    TOTAL = {r['total_score']}/100    tier={r['tier']}")
    print("=" * 68)
    # readable breakdown
    for dim, d in r["dimension_scores"].items():
        print(f"\n{dim:14s}  {d['score']}/{d['max']}")
        for c in d["criteria"]:
            g = grade(c["points"], c["max"])
            print(f"   [{g:>4}]  {c['label']:44s} {c['points']:>5}/{c['max']}")

    # LaTeX rows for Table 4 (Dimension / criterion & Grade & Pts & Max)
    print("\n--- LaTeX rows (" + study_id + ") ---")
    for dim, d in r["dimension_scores"].items():
        print(f"\\textbf{{{dim}}} & & \\textbf{{{d['score']}}} & \\textbf{{{d['max']}}} \\\\")
        for c in d["criteria"]:
            g = grade(c["points"], c["max"])
            print(f"\\quad {c['label']} & {g} & {c['points']} & {c['max']} \\\\")
    print(f"\\textbf{{Total}} & & \\textbf{{{r['total_score']}}} & \\textbf{{100}} \\\\")


if __name__ == "__main__":
    ids = sys.argv[1:]
    if not ids:
        print("usage: python -m scripts.dump_fair_r <study_id> [<study_id> ...]")
        raise SystemExit(1)
    for sid in ids:
        dump(sid)
