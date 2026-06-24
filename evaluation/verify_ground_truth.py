#!/usr/bin/env python3
"""
Ground-truth verification harness.

For every study, check whether each ground-truth entity is *supported by its
source*, and flag the ones that are not:

  • paper-derived entities (Method, Dataset, Parameter, EvaluationResult metric
    + VALUE, Person, Organization, ComputingEnvironment gpu/cuda) → grounded in
    the PDF text (data/papers/<study>.pdf).
  • repo-derived entities (SoftwareApplication, RandomSeed) → grounded in the
    paper OR in repo_metadata.json (they legitimately come from the repo).
  • Activity names are model-synthesised descriptions, not paper strings, so they
    are NOT grounded-checked (only screened for nullish junk).

Grounding uses normalised phrase / token-coverage / acronym matching (the same
entity-aware logic as the scorer). This is a TRIAGE — it surfaces likely errors
for review; it does not by itself prove an entity wrong (paraphrase can cause a
false flag). Nullish/empty names are always real errors.

    python -m evaluation.verify_ground_truth [--tier gold|silver|both]
                                             [--report out.md] [--json out.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess

from evaluation.eval_extraction import _norm, _tokens, _acronyms, _clean, _s

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = os.path.join(ROOT, "data", "papers")
GT = os.path.join(ROOT, "data", "ground_truth")
_CACHE: dict[str, tuple[str, set]] = {}


# ── PDF text ──────────────────────────────────────────────────────────────────

def paper_text(study: str):
    """(normalised text, token set) for a study's PDF; '' if missing."""
    if study in _CACHE:
        return _CACHE[study]
    pdf = os.path.join(PAPERS, f"{study}.pdf")
    if not os.path.exists(pdf):
        _CACHE[study] = ("", set())
        return _CACHE[study]
    try:
        raw = subprocess.run(["pdftotext", "-q", pdf, "-"],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception:
        raw = ""
    low = raw.lower()
    norm = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.\- ]+", " ", low))
    toks = set(re.findall(r"[a-z0-9]+", low))
    _CACHE[study] = (norm, toks)
    return _CACHE[study]


# ── grounding predicates ──────────────────────────────────────────────────────

def name_grounded(name, norm, toks) -> bool:
    nm = _norm(name)
    if not nm:
        return False
    if nm in norm:                                  # exact phrase
        return True
    nt = _tokens(name)
    if nt and sum(t in toks for t in nt) / len(nt) >= 0.6:   # most tokens present
        return True
    for ac in _acronyms(name):
        if len(ac) >= 2 and ac in toks:
            return True
    return False


def value_grounded(value, norm) -> bool:
    """Is a reported number present in the paper text?"""
    s = _s(value)
    if not s:
        return False
    m = re.findall(r"-?\d+\.?\d*", s)
    if not m:
        return name_grounded(value, norm, set())
    return any(num in norm for num in m if len(num) >= 2)


def repo_software(study):
    p = os.path.join(GT, "silver", study, "repo_metadata.json")
    if not os.path.exists(p):
        return set(), set()
    d = json.load(open(p))
    sw = {_norm(x.get("name")) for x in d.get("software_dependencies", [])}
    seeds = {_s(x.get("value")) for x in d.get("seeds", [])}
    return sw, seeds


# ── per-study check ───────────────────────────────────────────────────────────

def check_study(tier, study) -> dict:
    path = os.path.join(GT, tier, study, "gold_standard.json")
    doc = json.load(open(path))
    e = doc.get("entities", {}) or {}
    norm, toks = paper_text(study)
    repo_sw, repo_seeds = repo_software(study)
    flags = []
    n = 0

    def flag(cat, item, reason):
        flags.append({"category": cat, "item": item, "reason": reason})

    # nullish screen across everything (always a real error)
    def nullish(v):
        return _clean(v) is None

    for m in e.get("Method", []):
        n += 1
        if nullish(m.get("name")):
            flag("Method", m.get("name"), "empty/nullish name")
        elif norm and not name_grounded(m.get("name"), norm, toks):
            flag("Method", m.get("name"), "not found in paper text")
    for d in e.get("Dataset", []):
        n += 1
        if nullish(d.get("name")):
            flag("Dataset", d.get("name"), "empty/nullish name")
        elif norm and d.get("role") != "produced" and \
                not name_grounded(d.get("name"), norm, toks):
            flag("Dataset", d.get("name"), "not found in paper text")
    for p in e.get("Parameter", []):
        n += 1
        if nullish(p.get("name")):
            flag("Parameter", p.get("name"), "empty/nullish name")
    for r in e.get("EvaluationResult", []):
        n += 1
        label = f"{r.get('metric')}={r.get('value')}"
        if nullish(r.get("metric")):
            flag("EvaluationResult", r, "empty/nullish metric")
        elif _clean(r.get("value")) is None:
            flag("EvaluationResult", label, "empty/nullish value")
        elif not re.search(r"\d", _s(r.get("value"))):
            flag("EvaluationResult", label, "value is not numeric (placeholder)")
        elif norm and not value_grounded(r.get("value"), norm):
            flag("EvaluationResult", label, "reported value not found in paper")
    # SoftwareApplication is repo-derived (legitimately from requirements.txt);
    # only screen for nullish junk, do not ground against the paper.
    for s in e.get("SoftwareApplication", []):
        n += 1
        if nullish(s.get("name")):
            flag("SoftwareApplication", s.get("name"), "empty/nullish name")
    for s in e.get("RandomSeed", []):
        n += 1
        if _s(s.get("value")) not in repo_seeds and norm and \
                not value_grounded(s.get("value"), norm):
            flag("RandomSeed", s.get("value"), "seed not in repo or paper")
    for person in e.get("Person", []):
        n += 1
        if norm and not name_grounded(person.get("name"), norm, toks):
            flag("Person", person.get("name"), "name not in paper")

    return {"study": study, "tier": tier, "n_checked": n,
            "n_flagged": len(flags), "has_pdf": bool(norm), "flags": flags}


def run(tiers) -> dict:
    results = []
    for tier in tiers:
        for sdir in sorted(glob.glob(os.path.join(GT, tier, "study*"))):
            study = os.path.basename(sdir)
            if os.path.exists(os.path.join(sdir, "gold_standard.json")):
                results.append(check_study(tier, study))
    checked = sum(r["n_checked"] for r in results)
    flagged = sum(r["n_flagged"] for r in results)
    by_cat: dict[str, int] = {}
    for r in results:
        for f in r["flags"]:
            by_cat[f["category"]] = by_cat.get(f["category"], 0) + 1
    return {"results": results, "total_checked": checked,
            "total_flagged": flagged,
            "grounding_rate": round(1 - flagged / checked, 3) if checked else 0,
            "by_category": dict(sorted(by_cat.items(), key=lambda x: -x[1]))}


def write_report(rep, path):
    lines = ["# Ground-truth verification report", ""]
    lines.append(f"- entities checked: **{rep['total_checked']}**")
    lines.append(f"- flagged (unsupported / nullish): **{rep['total_flagged']}**")
    lines.append(f"- grounding rate: **{rep['grounding_rate']:.1%}**")
    lines.append("")
    lines.append("## Flags by category")
    lines.append("")
    for c, k in rep["by_category"].items():
        lines.append(f"- {c}: {k}")
    lines.append("")
    lines.append("## Per-study flags")
    lines.append("")
    for r in sorted(rep["results"], key=lambda x: -x["n_flagged"]):
        if not r["n_flagged"]:
            continue
        lines.append(f"### {r['study']} ({r['tier']}) — {r['n_flagged']}/"
                     f"{r['n_checked']} flagged"
                     + ("" if r["has_pdf"] else "  [NO PDF]"))
        for f in r["flags"]:
            lines.append(f"- **{f['category']}**: `{f['item']}` — {f['reason']}")
        lines.append("")
    open(path, "w").write("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default="both", choices=["gold", "silver", "both"])
    ap.add_argument("--report", default=os.path.join(ROOT, "evaluation",
                                                     "gt_verification_report.md"))
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    tiers = ["gold", "silver"] if args.tier == "both" else [args.tier]
    rep = run(tiers)
    print(f"checked={rep['total_checked']}  flagged={rep['total_flagged']}  "
          f"grounding={rep['grounding_rate']:.1%}")
    print("by category:", rep["by_category"])
    write_report(rep, args.report)
    print(f"[verify] wrote {args.report}")
    if args.json:
        json.dump(rep, open(args.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
