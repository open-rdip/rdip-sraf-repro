#!/usr/bin/env python3
"""
Build the result-reproducibility manifest (RQ #20).

Joins the full-tier repos (validation/repo_list.csv, final_tier == 'full') with
the *claimed* evaluation results from the ground truth (gold preferred, else
silver). Emits a YAML manifest with one entry per repo: the paper's claimed
numbers plus blank `run.command` / `obtained` fields for you to fill while
executing each repo on the cluster.

    python -m result_repro.generate_manifest [--out result_repro/manifest.yaml]

The manifest is the contract for compare_results.py, which classifies each repo
as reproduced / mismatch / run_failed once `obtained` is filled in.
"""
from __future__ import annotations

import argparse
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_LIST = os.path.join(ROOT, "validation", "repo_list.csv")
GT = os.path.join(ROOT, "data", "ground_truth")


def claimed_results(study: str) -> list[dict]:
    """Paper-claimed eval results, gold preferred then silver."""
    for tier in ("gold", "silver"):
        p = os.path.join(GT, tier, study, "gold_standard.json")
        if os.path.exists(p):
            ev = json.load(open(p)).get("entities", {}).get("EvaluationResult", [])
            out = []
            for r in ev:
                out.append({"metric": r.get("metric"), "claimed": r.get("value"),
                            "split": r.get("split"), "dataset": r.get("dataset"),
                            "source_tier": tier})
            if out:
                return out
            return out
    return []


def build_manifest() -> list[dict]:
    rows = list(csv.DictReader(open(REPO_LIST)))
    full = [r for r in rows if r.get("final_tier") == "full"]
    manifest = []
    for r in full:
        sid = r["study_id"]
        manifest.append({
            "study_id": sid,
            "repo_url": r.get("repo_url"),
            "paper_title": r.get("paper_title"),
            "language": r.get("language"),
            "claimed": claimed_results(sid),
            # —— to fill while running ——
            "run": {"command": "", "gpu": True, "data_ready": False,
                    "est_minutes": None, "notes": ""},
            "obtained": [],     # [{metric, value, split}] captured from the run log
            "status": "pending",  # pending | reproduced | partial | mismatch | run_failed | skipped
        })
    return manifest


def to_yaml(manifest: list[dict]) -> str:
    """Minimal YAML writer (no PyYAML dependency for writing)."""
    def esc(v):
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v).replace('"', '\\"')
        return f'"{s}"'

    lines = ["# Result-reproducibility manifest (RQ #20)",
             "# Fill run.command + obtained[] per repo, then run compare_results.py", ""]
    for m in manifest:
        lines.append(f"- study_id: {esc(m['study_id'])}")
        lines.append(f"  repo_url: {esc(m['repo_url'])}")
        lines.append(f"  paper_title: {esc(m['paper_title'])}")
        lines.append(f"  language: {esc(m['language'])}")
        lines.append(f"  status: {esc(m['status'])}")
        lines.append("  claimed:")
        if m["claimed"]:
            for c in m["claimed"]:
                lines.append(f"    - {{metric: {esc(c['metric'])}, claimed: {esc(c['claimed'])}, "
                             f"split: {esc(c['split'])}, dataset: {esc(c['dataset'])}}}")
        else:
            lines.append("    []   # no claimed numbers in ground truth")
        run = m["run"]
        lines.append("  run:")
        lines.append(f"    command: {esc(run['command'])}")
        lines.append(f"    gpu: {esc(run['gpu'])}")
        lines.append(f"    data_ready: {esc(run['data_ready'])}")
        lines.append(f"    est_minutes: {esc(run['est_minutes'])}")
        lines.append(f"    notes: {esc(run['notes'])}")
        lines.append("  obtained: []   # - {metric: ..., value: ..., split: ...}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(ROOT, "result_repro", "manifest.yaml"))
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    manifest = build_manifest()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, "w").write(to_yaml(manifest))
    n_claims = sum(len(m["claimed"]) for m in manifest)
    print(f"{len(manifest)} full-tier repos, {n_claims} claimed results → {args.out}")
    if args.json:
        json.dump(manifest, open(args.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
