"""Turn result_repro/results/summary.json into a paper-ready report.

Produces the build->recipe->run->reproduce funnel, the blocker taxonomy (grouped),
and a one-row-per-repo table. Writes result_repro/results/report.md and prints it.

  ~/envs/sraf/bin/python -m result_repro.summarize
"""
from __future__ import annotations

import json
import os
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "result_repro", "results")


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
    return reason or "—"


def main() -> int:
    data = json.load(open(os.path.join(RESULTS, "summary.json")))
    rows = data["rows"]
    n = len(rows)
    n_skip = sum(r["status"] == "skipped" for r in rows)
    n_recipe = sum(bool(r.get("recipe_command")) for r in rows)
    ran = [r for r in rows if r["status"] in ("reproduced", "partial", "mismatch")]
    n_repro = sum(r["status"] == "reproduced" for r in rows)

    fam = Counter(_family(r.get("reason", "")) for r in rows
                  if r["status"] in ("skipped", "run_failed"))

    L = []
    L.append("# Result-level reproduction — report\n")
    L.append("## Funnel\n")
    L.append(f"- Buildable (full-tier) repos: **{n}**")
    L.append(f"- Attempted (not pre-skipped): **{n - n_skip}**")
    L.append(f"- Execution recipe extracted: **{n_recipe}**")
    L.append(f"- Actually ran (produced output): **{len(ran)}**")
    L.append(f"- Reproduced headline number within tolerance: **{n_repro}**")
    if ran:
        L.append(f"- Reproduced / ran: **{n_repro}/{len(ran)} "
                 f"({n_repro/len(ran):.0%})**")
    L.append("\n## Blocker taxonomy\n")
    L.append("| Blocker | Count |")
    L.append("|---|---:|")
    for k, v in fam.most_common():
        L.append(f"| {k} | {v} |")

    L.append("\n## Per-repo outcome\n")
    L.append("| study | recipe | status | blocker / result | claimed | obtained |")
    L.append("|---|:--:|---|---|---|---|")
    for r in rows:
        claimed = "; ".join(f"{c.get('metric')}={c.get('claimed')}"
                            for c in (r.get("claimed") or [])) or "—"
        obtained = "; ".join(f"{o.get('metric')}={o.get('value')}"
                             for o in (r.get("obtained") or [])) or "—"
        rec = "yes" if r.get("recipe_command") else "no"
        detail = r.get("reason") or ""
        if r["status"] in ("reproduced", "partial", "mismatch"):
            detail = r["status"]
        L.append(f"| {r['study_id']} | {rec} | {r['status']} | {detail} | "
                 f"{claimed[:40]} | {obtained[:30]} |")

    report = "\n".join(L) + "\n"
    open(os.path.join(RESULTS, "report.md"), "w").write(report)
    print(report)
    print(f"[summarize] wrote {RESULTS}/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
