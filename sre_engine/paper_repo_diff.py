"""Paper-vs-repository semantic diff (contribution N4).

`run_diff(original, reproduction)` in diff_engine.py compares two *runs*. This
compares what a paper CLAIMS against what its repository DOES, which is the
comparison the corpus can actually support today: no study in the corpus reached
a second run, but every study has a paper extraction and a cloned repository.

    run_paper_repo_diff("study003", "qwen-qwen2-5-14b-instruct-gptq-int8")

Inputs, all already on disk:

    data/extractions/<study>__<slug>.json          paper side (LLM extraction)
    validation/repo_facts/<study>.json             repo side (datasets, hp,
                                                   metrics, seeds — deterministic)
    data/ground_truth/*/<study>/repo_metadata.json repo side (dependencies,
                                                   seeds — deterministic)

## Two design rules, both load-bearing for the evaluation

**No language model in the alignment step.** Normalisation is case-folding,
punctuation stripping and the curated alias tables in `repo_facts`. A model in
the matcher would reintroduce the extraction-quality confound the paper is
trying to measure: a missed conflict could then be the detector's fault or the
matcher's, and no reviewer could tell which. The alias table is auditable.

**Silence is not agreement.** A conflict is only emitted when BOTH sides state
something comparable. Every conflict type therefore reports a `decidability`
alongside its verdict — `decidable`, `paper_silent`, `repo_silent`,
`both_silent`. Without it, precision and recall over the corpus would silently
count "we could not tell" as "no conflict", which is the single easiest way to
report a flattering and meaningless number.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "build_harness"))

from repo_facts import (  # noqa: E402
    DATASET_ALIASES, HP_ALIASES, METRIC_ALIASES, _canon,
)

DIFF_VERSION = 1

EXTRACTIONS = ROOT / "data" / "extractions"
REPO_FACTS = Path(os.getenv("REPO_FACTS_OUT", ROOT / "validation" / "repo_facts"))
GROUND_TRUTH = ROOT / "data" / "ground_truth"

DECIDABLE, PAPER_SILENT, REPO_SILENT, BOTH_SILENT = (
    "decidable", "paper_silent", "repo_silent", "both_silent")


# ── loading ──────────────────────────────────────────────────────────────────

def load_paper(study_id: str, model_slug: str) -> dict | None:
    p = EXTRACTIONS / f"{study_id}__{model_slug}.json"
    if not p.exists():
        return None
    return (json.loads(p.read_text()) or {}).get("metadata") or {}


def load_repo_facts(study_id: str) -> dict | None:
    p = REPO_FACTS / f"{study_id}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    return d if d.get("status") == "ok" else None


def load_repo_metadata(study_id: str) -> dict:
    """Deterministic dependency/seed facts from the lifter parsers."""
    for tier in ("gold", "silver"):
        p = GROUND_TRUTH / tier / study_id / "repo_metadata.json"
        if p.exists():
            return json.loads(p.read_text())
    return {}


def available_slugs() -> list[str]:
    out = set()
    for p in EXTRACTIONS.glob("*__*.json"):
        out.add(p.stem.split("__", 1)[1])
    return sorted(out)


# ── normalisation ────────────────────────────────────────────────────────────

_NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$")


def _canon_set(values, table) -> set[str]:
    out, _ = _canon_set_with_misses(values, table)
    return out


def _canon_set_with_misses(values, table) -> tuple[set[str], list[str]]:
    """Also return the surface forms no alias recognised.

    An unrecognised name is dropped rather than treated as a claim, which keeps
    precision honest but makes the diff blind to it. study003 claims AP50, AP75
    and APm; none is in METRIC_ALIASES, so three of its four claimed metrics
    disappear before comparison. Silently discarding them would let the corpus
    report high decidability while most claims were never actually examined, so
    the misses are counted and reported.
    """
    out, misses = set(), []
    for v in values:
        sv = str(v or "").strip()
        if not sv:
            continue
        c = _canon(sv, table)
        (out.add(c) if c else misses.append(sv))
    return out, misses


def _as_number(v):
    s = str(v).strip().strip("%").replace(",", "")
    return float(s) if _NUM_RE.match(s) else None


def _values_agree(a, b) -> bool:
    """Numeric when both parse as numbers (so 0.0003 == 3e-4), else case-folded
    string equality. Deliberately strict: a loose matcher inflates precision."""
    na, nb = _as_number(a), _as_number(b)
    if na is not None and nb is not None:
        if na == nb:
            return True
        scale = max(abs(na), abs(nb), 1e-12)
        return abs(na - nb) / scale < 1e-6
    return re.sub(r"[\s_\-]+", "", str(a).strip().lower()) == \
           re.sub(r"[\s_\-]+", "", str(b).strip().lower())


def _dep_key(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(name).strip().lower())


# ── conflict detectors ───────────────────────────────────────────────────────

def _diff_datasets(paper, facts, misses=None) -> tuple[str, list[dict]]:
    P, miss = _canon_set_with_misses(
        [d.get("name") for d in paper.get("datasets") or []], DATASET_ALIASES)
    if misses is not None:
        misses["dataset"] = miss
    R = _canon_set([d.get("canonical") for d in facts.get("datasets") or []], DATASET_ALIASES)
    if not P and not R:
        return BOTH_SILENT, []
    if not P:
        return PAPER_SILENT, []
    if not R:
        return REPO_SILENT, []
    if P & R:
        return DECIDABLE, []
    # Disjoint, not per-dataset: papers routinely name datasets they only
    # compare against, so a single missing name is weak evidence. No overlap at
    # all is the signal that the repository implements something else.
    return DECIDABLE, [{
        "type": "dataset_mismatch",
        "paper": sorted(P), "repo": sorted(R),
        "detail": "no canonical dataset is named on both sides",
    }]


def _diff_hyperparameters(paper, facts) -> tuple[str, list[dict]]:
    P: dict[str, str] = {}
    for h in paper.get("hyperparameters") or []:
        c = _canon(str(h.get("name", "")), HP_ALIASES)
        if c and h.get("value") not in (None, ""):
            P.setdefault(c, str(h["value"]))
    R: dict[str, dict] = {}
    for h in facts.get("hyperparameters") or []:
        c = h.get("canonical")
        if c and h.get("value") not in (None, ""):
            R.setdefault(c, h)

    if not P and not R:
        return BOTH_SILENT, []
    if not P:
        return PAPER_SILENT, []
    if not R:
        return REPO_SILENT, []
    shared = set(P) & set(R)
    if not shared:
        # Both sides speak, but never about the same hyperparameter.
        return REPO_SILENT, []
    out = []
    for name in sorted(shared):
        if not _values_agree(P[name], R[name]["value"]):
            out.append({
                "type": "hyperparameter_mismatch", "name": name,
                "paper": P[name], "repo": R[name]["value"],
                "detail": R[name].get("evidence", ""),
            })
    return DECIDABLE, out


def _diff_metrics(paper, facts, misses=None) -> tuple[str, list[dict]]:
    P, miss = _canon_set_with_misses(
        [e.get("metric") for e in paper.get("evaluation_results") or []],
        METRIC_ALIASES)
    if misses is not None:
        misses["metric"] = miss
    R = {m["canonical"]: m for m in facts.get("metrics") or [] if m.get("canonical")}
    if not P and not R:
        return BOTH_SILENT, []
    if not P:
        return PAPER_SILENT, []
    if not R:
        # The repository exposes no machine-identifiable metric computation at
        # all, so "never computed" is undecidable rather than true. Counting it
        # as a conflict would manufacture the paper's own headline result.
        return REPO_SILENT, []
    return DECIDABLE, [{
        "type": "metric_never_computed", "name": m,
        "paper": m, "repo": sorted(R),
        "detail": "claimed metric has no detected computation in the repository",
    } for m in sorted(P - set(R))]


def _diff_dependencies(paper, meta) -> tuple[str, list[dict]]:
    P = {}
    for d in paper.get("dependencies") or []:
        v = (d.get("version") or "").strip()
        # "[54]" is a citation marker the extractor mistook for a version.
        if v and not re.fullmatch(r"\[?\d+\]?", v):
            P[_dep_key(d.get("name", ""))] = v
    R = {}
    for d in meta.get("software_dependencies") or []:
        v = (d.get("version") or "").strip()
        if v:
            R[_dep_key(d.get("name", ""))] = v
    if not P and not R:
        return BOTH_SILENT, []
    if not P:
        return PAPER_SILENT, []
    if not R:
        return REPO_SILENT, []
    shared = set(P) & set(R)
    if not shared:
        return REPO_SILENT, []
    return DECIDABLE, [{
        "type": "dependency_version_mismatch", "name": n,
        "paper": P[n], "repo": R[n],
    } for n in sorted(shared) if not _values_agree(P[n], R[n])]


def _diff_seeds(paper, facts, meta) -> tuple[str, list[dict]]:
    P = {str(s).strip() for s in (paper.get("random_seeds") or []) if str(s).strip()}
    R = {str(s.get("value")).strip() for s in (facts.get("seeds") or [])}
    R |= {str(s.get("value")).strip() for s in (meta.get("seeds") or [])}
    R.discard("None")
    R.discard("")
    if not P and not R:
        return BOTH_SILENT, []
    if not P:
        return PAPER_SILENT, []
    if not R:
        return REPO_SILENT, []
    if P & R:
        return DECIDABLE, []
    return DECIDABLE, [{
        "type": "seed_mismatch",
        "paper": sorted(P), "repo": sorted(R),
        "detail": "no seed value declared in the paper is set anywhere in the code",
    }]


# ── entry point ──────────────────────────────────────────────────────────────

def run_paper_repo_diff(study_id: str, model_slug: str) -> dict:
    paper = load_paper(study_id, model_slug)
    facts = load_repo_facts(study_id)
    meta = load_repo_metadata(study_id)

    rec = {"study_id": study_id, "model_slug": model_slug,
           "diff_version": DIFF_VERSION, "status": "ok",
           "conflicts": [], "decidability": {}}

    if paper is None:
        rec.update(status="no_extraction")
        return rec
    if facts is None:
        rec.update(status="no_repo_facts")
        return rec

    misses: dict[str, list[str]] = {}
    parts = {
        "dataset": _diff_datasets(paper, facts, misses),
        "hyperparameter": _diff_hyperparameters(paper, facts),
        "metric": _diff_metrics(paper, facts, misses),
        "dependency": _diff_dependencies(paper, meta),
        "seed": _diff_seeds(paper, facts, meta),
    }
    for kind, (decidability, conflicts) in parts.items():
        rec["decidability"][kind] = decidability
        rec["conflicts"].extend(conflicts)

    rec["unmapped_paper_names"] = {k: v for k, v in misses.items() if v}
    rec["counts"] = {
        "conflicts": len(rec["conflicts"]),
        "unmapped_paper_names": sum(len(v) for v in misses.values()),
        "decidable_types": sum(1 for v in rec["decidability"].values() if v == DECIDABLE),
    }
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="model slug, as in data/extractions/")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--study")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--json", help="write all records to this file")
    a = ap.parse_args()

    if a.model not in available_slugs():
        print(f"unknown model slug. available: {', '.join(available_slugs())}")
        return 1

    if a.study:
        studies = [a.study]
    else:
        studies = sorted({p.stem.split("__", 1)[0]
                          for p in EXTRACTIONS.glob(f"*__{a.model}.json")})

    records, tally = [], {}
    for sid in studies:
        rec = run_paper_repo_diff(sid, a.model)
        records.append(rec)
        if rec["status"] != "ok":
            print(f"  {sid}: {rec['status']}")
            continue
        for c in rec["conflicts"]:
            tally[c["type"]] = tally.get(c["type"], 0) + 1
        flags = "".join(k[0].upper() if v == DECIDABLE else "."
                        for k, v in sorted(rec["decidability"].items()))
        print(f"  {sid}: {rec['counts']['conflicts']} conflict(s)  [{flags}]")
        for c in rec["conflicts"]:
            label = f" {c['name']}" if c.get("name") else ""
            print(f"      {c['type']}{label}: paper={c['paper']} repo={c['repo']}")

    ok = [r for r in records if r["status"] == "ok"]
    print(f"\n{len(ok)}/{len(records)} studies diffed.")
    if ok:
        print("conflicts by type:", tally or "none")
        print("decidability by type:")
        for kind in ("dataset", "hyperparameter", "metric", "dependency", "seed"):
            n = sum(1 for r in ok if r["decidability"].get(kind) == DECIDABLE)
            print(f"  {kind:16s} decidable in {n:3d}/{len(ok)} studies")
        unmapped = sum(r.get("counts", {}).get("unmapped_paper_names", 0) for r in ok)
        print(f"paper names no alias table recognised: {unmapped} "
              f"(these were dropped before comparison, not counted as agreement)")
    if a.json:
        Path(a.json).write_text(json.dumps(records, indent=2))
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
