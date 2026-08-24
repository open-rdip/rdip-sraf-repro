"""Turn the cached per-study rows into a paper-ready report.

Aggregates EVERY row in result_repro/results/rows/*.json (falling back to
summary.json) and splits them into two funnels that must stay separate in the
paper:
  - corpus       : study*  (the 96-corpus population -> funnel + taxonomy)
  - validation   : ctrl_*  (known-reproducible positive controls -> engine works)

Because it reads the per-study row cache, it does not matter which manifest was
run last; summary.json being overwritten by a validation run is harmless.

  ~/envs/sraf/bin/python -m result_repro.summarize
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "result_repro", "results")
ROWS_DIR = os.path.join(RESULTS, "rows")


def _family(reason: str) -> str:
    """Group a fine-grained reason into a headline blocker family."""
    r = (reason or "").lower()
    if r.startswith("skip"):
        if "mismatch" in r:
            return "repo/paper mismatch"
        if "out-of-scale" in r or "beyond" in r:
            return "out of compute scale"
        if "no claimed" in r or "no numeric" in r:
            return "no numeric claim"
        if "hardware" in r or "throughput" in r or "processing time" in r:
            return "hardware-bound metric"
        if "production" in r:
            return "production/online metric"
        if "device" in r or "api" in r:
            return "external device/API"
        return "skipped (other)"
    if r == "no_recipe":
        return "no documented recipe"
    if r == "placeholder_recipe":
        return "placeholder recipe"
    if r == "recipe_missing (run extract_recipes first)":
        return "recipe not extracted"
    if r.startswith("missing_dependency"):
        return "missing python dependency"
    if r.startswith("missing_system_dep") or r.startswith("missing_tool"):
        return "missing system dependency"
    if r.startswith("dead_download") or r.startswith("gated_download"):
        return "dead/gated download (link rot)"
    if r.startswith("install_build_error"):
        return "broken install/build"
    if r == "gpu_oom":
        return "GPU out of memory"
    if r == "auth_ssh":
        return "auth/SSH clone"
    if r.startswith("missing_file"):
        return "missing data/file"
    if r == "no_metric_in_log":
        return "ran, metric not parsed"
    if r.startswith("run_error"):
        return "run error (other)"
    return reason or "-"


def _load_rows() -> list:
    """Prefer the per-study row cache; fall back to summary.json."""
    rows, seen = [], set()
    for p in sorted(glob.glob(os.path.join(ROWS_DIR, "*.json"))):
        try:
            r = json.load(open(p))
        except (OSError, ValueError):
            continue
        if r.get("study_id") and r["study_id"] not in seen:
            seen.add(r["study_id"])
            rows.append(r)
    if not rows:
        sj = os.path.join(RESULTS, "summary.json")
        if os.path.isfile(sj):
            rows = json.load(open(sj)).get("rows", [])
    return rows


def _funnel(rows: list, title: str) -> list:
    n = len(rows)
    n_skip = sum(r["status"] == "skipped" for r in rows)
    n_recipe = sum(bool(r.get("recipe_command")) for r in rows)
    ran = [r for r in rows if r["status"] in ("reproduced", "partial", "mismatch")]
    n_repro = sum(r["status"] == "reproduced" for r in rows)
    L = [f"## {title} - funnel\n"]
    L.append(f"- Repos considered: **{n}**")
    L.append(f"- Attempted (not pre-skipped): **{n - n_skip}**")
    L.append(f"- Execution recipe extracted: **{n_recipe}**")
    L.append(f"- Actually ran (produced output): **{len(ran)}**")
    L.append(f"- Reproduced headline number within tolerance: **{n_repro}**")
    if ran:
        L.append(f"- Reproduced / ran: **{n_repro}/{len(ran)} ({n_repro/len(ran):.0%})**")
    return L


def _taxonomy(rows: list) -> list:
    fam = Counter(_family(r.get("reason", "")) for r in rows
                  if r["status"] in ("skipped", "run_failed"))
    L = ["\n## Blocker taxonomy (corpus)\n", "| Blocker | Count |", "|---|---:|"]
    for k, v in fam.most_common():
        L.append(f"| {k} | {v} |")
    return L


def _table(rows: list, title: str) -> list:
    L = [f"\n## {title} - per-repo outcome\n",
         "| study | recipe | status | blocker / result | claimed | obtained |",
         "|---|:--:|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: x["study_id"]):
        claimed = "; ".join(f"{c.get('metric')}={c.get('claimed')}"
                            for c in (r.get("claimed") or [])) or "-"
        obtained = "; ".join(f"{o.get('metric')}={o.get('value')}"
                             for o in (r.get("obtained") or [])) or "-"
        rec = "yes" if r.get("recipe_command") else "no"
        detail = r.get("reason") or ""
        if r["status"] in ("reproduced", "partial", "mismatch"):
            detail = r["status"]
        L.append(f"| {r['study_id']} | {rec} | {r['status']} | {detail} | "
                 f"{claimed[:40]} | {obtained[:30]} |")
    return L


def main() -> int:
    rows = _load_rows()
    corpus = [r for r in rows if not str(r.get("study_id", "")).startswith("ctrl_")]
    validation = [r for r in rows if str(r.get("study_id", "")).startswith("ctrl_")]

    L = ["# Result-level reproduction - report\n"]
    L += _funnel(corpus, "Corpus (96)")
    L += _taxonomy(corpus)
    L += _table(corpus, "Corpus")
    if validation:
        L.append("\n---\n")
        L += _funnel(validation, "Validation / positive controls")
        L += _table(validation, "Validation")
    else:
        L.append("\n_(No validation/positive-control rows yet. Run the validation "
                 "manifest to populate the engine-works check.)_")

    report = "\n".join(L) + "\n"
    os.makedirs(RESULTS, exist_ok=True)
    open(os.path.join(RESULTS, "report.md"), "w").write(report)
    print(report)
    print(f"[summarize] wrote {RESULTS}/report.md "
          f"({len(corpus)} corpus, {len(validation)} validation rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
