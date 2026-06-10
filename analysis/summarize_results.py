"""Aggregate build-harness result JSONs into meeting-ready summary stats.

Reads validation/results/*.json (one per processed repo) and emits:
  - a console summary
  - analysis/results_summary.md  (tables you can paste into slides)
  - analysis/results_summary.csv (one row per repo)

Pure stdlib — runs anywhere, including the cluster login node via:
  ~/envs/sraf/bin/python -m analysis.summarize_results
"""
from __future__ import annotations
import csv
import glob
import json
import os
import statistics as stat
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(os.getenv("SRAF_RESULTS_DIR", REPO_ROOT / "validation" / "results"))
OUT_DIR = REPO_ROOT / "analysis"


def _load() -> list[dict]:
    out = []
    for p in sorted(glob.glob(str(RESULTS_DIR / "*.json"))):
        try:
            out.append(json.load(open(p)))
        except Exception as e:  # noqa: BLE001
            print(f"  skip {p}: {e}")
    return out


def _pct(n, d) -> str:
    return f"{(100*n/d):.1f}%" if d else "—"


def _row(r: dict) -> dict:
    a = r.get("artifacts", {}) or {}
    b = r.get("build", {}) or {}
    f = r.get("fair_r", {}) or {}
    lift = r.get("lift", {}) or {}
    meta = r.get("repo_meta", {}) or {}
    by_type = a.get("by_type", {}) or {}
    return {
        "study_id": r.get("study_id", ""),
        "status": r.get("status", ""),
        "n_artifacts": a.get("n_found", 0),
        "depth_note": a.get("depth_note", ""),
        "has_env_file": bool(by_type),
        "has_docker": "docker" in by_type,
        "has_conda": "conda" in by_type,
        "has_pip": "pip" in by_type,
        "triples": lift.get("triples", 0),
        "resolve_success": b.get("resolve_success"),
        "build_success": b.get("build_success"),
        "stage_failed": b.get("stage_failed"),
        "fair_r": f.get("total_score"),
        "tier": f.get("tier"),
        "license": meta.get("software_license"),
        "has_commit": bool(meta.get("commit_hash")),
    }


def summarize(rows: list[dict]) -> list[str]:
    n = len(rows)
    lines = [f"# SRAF corpus results — {n} repos processed\n"]

    # status
    lines.append("## Processing status\n")
    for k, v in Counter(r["status"] for r in rows).most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")

    # build outcomes (only repos where a build was attempted)
    attempted = [r for r in rows if r["resolve_success"] is not None]
    res_ok = sum(1 for r in attempted if r["resolve_success"])
    bld_ok = sum(1 for r in attempted if r["build_success"])
    lines.append("## Reproducibility outcomes (environment reconstruction)\n")
    lines.append(f"- Build attempted: {len(attempted)}/{n}")
    lines.append(f"- Tier 1 — resolution succeeds: {res_ok}/{len(attempted)} ({_pct(res_ok, len(attempted))})")
    lines.append(f"- Tier 2 — build succeeds:      {bld_ok}/{len(attempted)} ({_pct(bld_ok, len(attempted))})")
    sf = Counter(r["stage_failed"] for r in attempted if r["stage_failed"])
    if sf:
        lines.append("- Failure stage breakdown: " + ", ".join(f"{k}={v}" for k, v in sf.most_common()))
    lines.append("")

    # FAIR-R
    scores = [r["fair_r"] for r in rows if isinstance(r["fair_r"], (int, float))]
    if scores:
        lines.append("## FAIR-R score\n")
        lines.append(f"- mean {stat.mean(scores):.1f} | median {stat.median(scores):.1f} "
                     f"| min {min(scores):.1f} | max {max(scores):.1f}")
        for k, v in Counter(r["tier"] for r in rows if r["tier"]).most_common():
            lines.append(f"- tier {k}: {v}")
        lines.append("")

    # artifact placement (the real-world finding)
    lines.append("## Artifact placement & presence\n")
    for k, v in Counter(r["depth_note"] for r in rows).most_common():
        lines.append(f"- depth `{k or 'n/a'}`: {v}")
    no_env = sum(1 for r in rows if not r["has_env_file"])
    lines.append(f"- repos with NO env files: {no_env}/{n} ({_pct(no_env, n)})")
    for t in ("docker", "conda", "pip"):
        c = sum(1 for r in rows if r[f"has_{t}"])
        lines.append(f"- has {t}: {c}/{n} ({_pct(c, n)})")
    lines.append("")

    # metadata signals
    lic = sum(1 for r in rows if r["license"])
    com = sum(1 for r in rows if r["has_commit"])
    trips = [r["triples"] for r in rows if r["triples"]]
    lines.append("## Recoverable metadata\n")
    lines.append(f"- license detected: {lic}/{n} ({_pct(lic, n)})")
    lines.append(f"- commit hash:      {com}/{n} ({_pct(com, n)})")
    if trips:
        lines.append(f"- triples/repo: mean {stat.mean(trips):.0f} | median {stat.median(trips):.0f}")
    lines.append("")
    return lines


def main():
    rows = [_row(r) for r in _load()]
    if not rows:
        print(f"No result JSONs in {RESULTS_DIR}")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # per-repo CSV
    csv_path = OUT_DIR / "results_summary.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # markdown report
    lines = summarize(rows)
    (OUT_DIR / "results_summary.md").write_text("\n".join(lines))

    print("\n".join(lines))
    print(f"\nWrote {csv_path} and {OUT_DIR/'results_summary.md'}")


if __name__ == "__main__":
    main()
