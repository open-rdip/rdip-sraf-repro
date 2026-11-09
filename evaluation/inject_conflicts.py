"""C1 — injected-conflict evaluation for the paper↔repo diff (N4).

The corpus sweep tells us how often conflicts are *observed*. It cannot tell us
whether the detector is any good, because nothing in the corpus carries a label
saying a conflict is really there. So plant them: take a study where a conflict
type is decidable and the two sides currently AGREE, introduce one known
divergence, and check whether the detector reports it — and only it.

Two halves, and the second is the one that makes the numbers mean anything:

  INJECTIONS      a real divergence is planted. The detector should fire, with
                  the right type. Measures recall and type confusion.
  EQUIVALENCES    a perturbation that changes the surface form but not the
                  meaning: 0.0003 -> 3e-4, "AdamW" -> "adamw", CIFAR-10 ->
                  cifar10. The detector should stay silent. Measures precision
                  against exactly the false positives a normalisation bug
                  produces.

Reporting recall without the equivalence half would reward a detector that fires
on everything. That detector scores 100% recall and is useless.

    python3 evaluation/inject_conflicts.py --model <slug>
    python3 evaluation/inject_conflicts.py --model <slug> --json out.json

Ground truth is exact because we planted it — which is what Tier-B could not
have, and why this contribution can be validated where the criterion set could
not.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sre_engine"))
sys.path.insert(0, str(ROOT / "build_harness"))

from paper_repo_diff import (  # noqa: E402
    DECIDABLE, EXTRACTIONS, _diff_datasets, _diff_dependencies,
    _diff_hyperparameters, _diff_metrics, _diff_seeds,
    load_paper, load_repo_facts, load_repo_metadata,
)

INJECT_VERSION = 1

# A canonical value chosen so it cannot collide with what a repo already has.
ALIEN_DATASET = "LSUN"
ALIEN_METRIC = "NDCG"
ALIEN_SEED = "987654321"


def _run_all(paper, facts, meta) -> tuple[dict, list[dict]]:
    parts = {
        "dataset": _diff_datasets(paper, facts),
        "hyperparameter": _diff_hyperparameters(paper, facts),
        "metric": _diff_metrics(paper, facts),
        "dependency": _diff_dependencies(paper, meta),
        "seed": _diff_seeds(paper, facts, meta),
    }
    dec = {k: v[0] for k, v in parts.items()}
    conflicts = [c for v in parts.values() for c in v[1]]
    return dec, conflicts


# ── injections: should be detected ───────────────────────────────────────────

def inject_dataset(paper, facts, meta):
    if any(d.get("canonical") == ALIEN_DATASET for d in facts.get("datasets") or []):
        return None
    p = copy.deepcopy(paper)
    p["datasets"] = [{"name": ALIEN_DATASET, "version": None}]
    return p, facts, meta, "dataset_mismatch"


def inject_hyperparameter(paper, facts, meta):
    """Change the paper's value for a hyperparameter both sides agree on."""
    repo = {h["canonical"]: h for h in facts.get("hyperparameters") or []
            if h.get("canonical")}
    p = copy.deepcopy(paper)
    for h in p.get("hyperparameters") or []:
        from repo_facts import HP_ALIASES
        from paper_repo_diff import _canon, _values_agree
        c = _canon(str(h.get("name", "")), HP_ALIASES)
        if c and c in repo and h.get("value") not in (None, ""):
            if _values_agree(h["value"], repo[c]["value"]):
                h["value"] = "999999"          # cannot equal a real setting
                return p, facts, meta, "hyperparameter_mismatch"
    return None


def inject_metric(paper, facts, meta):
    if any(m.get("canonical") == ALIEN_METRIC for m in facts.get("metrics") or []):
        return None
    p = copy.deepcopy(paper)
    p.setdefault("evaluation_results", [])
    p["evaluation_results"] = list(p["evaluation_results"]) + [
        {"metric": ALIEN_METRIC, "value": "0.5", "split": None}]
    return p, facts, meta, "metric_never_computed"


def inject_seed(paper, facts, meta):
    p = copy.deepcopy(paper)
    p["random_seeds"] = [ALIEN_SEED]
    return p, facts, meta, "seed_mismatch"


# ── equivalences: should NOT be detected ─────────────────────────────────────

def equiv_hyperparameter_notation(paper, facts, meta):
    """Rewrite an agreeing numeric value in a different but equal notation.
    0.0003 and 3e-4 are the same number; a detector that flags this is broken."""
    from repo_facts import HP_ALIASES
    from paper_repo_diff import _canon, _values_agree
    repo = {h["canonical"]: h for h in facts.get("hyperparameters") or []
            if h.get("canonical")}
    p = copy.deepcopy(paper)
    for h in p.get("hyperparameters") or []:
        c = _canon(str(h.get("name", "")), HP_ALIASES)
        if not (c and c in repo):
            continue
        try:
            v = float(str(h.get("value")).strip())
        except (TypeError, ValueError):
            continue
        if _values_agree(h["value"], repo[c]["value"]):
            h["value"] = f"{v:.10e}"           # same number, different notation
            return p, facts, meta, "hyperparameter"
    return None


def equiv_dataset_case(paper, facts, meta):
    """Lowercase and de-punctuate an agreeing dataset name: CIFAR-10 -> cifar10."""
    repo = {d.get("canonical") for d in facts.get("datasets") or []}
    p = copy.deepcopy(paper)
    from repo_facts import DATASET_ALIASES
    from paper_repo_diff import _canon
    for d in p.get("datasets") or []:
        c = _canon(str(d.get("name", "")), DATASET_ALIASES)
        if c and c in repo:
            d["name"] = str(d["name"]).lower().replace("-", "").replace(" ", "")
            return p, facts, meta, "dataset"
    return None


def equiv_seed_whitespace(paper, facts, meta):
    """An agreeing seed, restated with padding. Still the same seed."""
    repo = {str(s.get("value")).strip() for s in (facts.get("seeds") or [])}
    repo |= {str(s.get("value")).strip() for s in (meta.get("seeds") or [])}
    for s in paper.get("random_seeds") or []:
        if str(s).strip() in repo:
            p = copy.deepcopy(paper)
            p["random_seeds"] = [f"  {str(s).strip()} "]
            return p, facts, meta, "seed"
    return None


INJECTIONS = {
    "dataset_mismatch": inject_dataset,
    "hyperparameter_mismatch": inject_hyperparameter,
    "metric_never_computed": inject_metric,
    "seed_mismatch": inject_seed,
}
EQUIVALENCES = {
    "hyperparameter_notation": equiv_hyperparameter_notation,
    "dataset_case": equiv_dataset_case,
    "seed_whitespace": equiv_seed_whitespace,
}
KIND_OF = {"dataset_mismatch": "dataset", "hyperparameter_mismatch": "hyperparameter",
           "metric_never_computed": "metric", "seed_mismatch": "seed"}


def evaluate(model_slug: str) -> dict:
    studies = sorted({p.stem.split("__", 1)[0]
                      for p in EXTRACTIONS.glob(f"*__{model_slug}.json")})

    tp = Counter(); fn = Counter(); eligible = Counter()
    confusion = defaultdict(Counter)          # planted type -> reported types
    extra = Counter()                         # unplanted conflicts alongside
    eq_total = Counter(); eq_false = Counter()
    eq_examples = defaultdict(list)

    for sid in studies:
        paper = load_paper(sid, model_slug)
        facts = load_repo_facts(sid)
        if paper is None or facts is None:
            continue
        meta = load_repo_metadata(sid)
        base_dec, base_conf = _run_all(paper, facts, meta)
        base_types = Counter(c["type"] for c in base_conf)

        # ── injections ───────────────────────────────────────────────────────
        for ctype, fn_inject in INJECTIONS.items():
            kind = KIND_OF[ctype]
            # Only inject where the type is decidable AND currently agrees,
            # otherwise a detection cannot be attributed to the injection.
            if base_dec.get(kind) != DECIDABLE or base_types.get(ctype):
                continue
            out = fn_inject(paper, facts, meta)
            if out is None:
                continue
            p2, f2, m2, planted = out
            eligible[ctype] += 1
            _, conf = _run_all(p2, f2, m2)
            got = Counter(c["type"] for c in conf)
            if got.get(planted):
                tp[planted] += 1
            else:
                fn[planted] += 1
            for t, n in got.items():
                confusion[planted][t] += n
                if t != planted and n > base_types.get(t, 0):
                    extra[planted] += n - base_types.get(t, 0)

        # ── equivalences ─────────────────────────────────────────────────────
        for name, fn_eq in EQUIVALENCES.items():
            out = fn_eq(paper, facts, meta)
            if out is None:
                continue
            p2, f2, m2, kind = out
            eq_total[name] += 1
            _, conf = _run_all(p2, f2, m2)
            new = [c for c in conf
                   if KIND_OF.get(c["type"]) == kind
                   and not any(b["type"] == c["type"] for b in base_conf)]
            if new:
                eq_false[name] += 1
                if len(eq_examples[name]) < 3:
                    eq_examples[name].append(
                        {"study": sid, "paper": new[0].get("paper"),
                         "repo": new[0].get("repo")})

    return {"inject_version": INJECT_VERSION, "model_slug": model_slug,
            "studies": len(studies),
            "recall": {t: {"planted": eligible[t], "detected": tp[t],
                           "missed": fn[t],
                           "recall": (tp[t] / eligible[t]) if eligible[t] else None}
                       for t in INJECTIONS},
            "collateral": dict(extra),
            "confusion": {k: dict(v) for k, v in confusion.items()},
            "equivalence": {n: {"tested": eq_total[n], "false_positives": eq_false[n],
                                "examples": eq_examples[n]} for n in EQUIVALENCES}}


def report(r: dict) -> None:
    print(f"\nC1 injected-conflict evaluation — {r['model_slug']}")
    print(f"{r['studies']} studies\n")
    print("RECALL (a real divergence was planted; the detector should fire)")
    print(f"  {'type':26s} {'planted':>8s} {'found':>7s} {'missed':>7s} {'recall':>8s}")
    for t, d in r["recall"].items():
        rec = "     n/a" if d["recall"] is None else f"{d['recall']:8.3f}"
        print(f"  {t:26s} {d['planted']:8d} {d['detected']:7d} {d['missed']:7d} {rec}")

    print("\nPRECISION (surface change only; the detector should stay silent)")
    print(f"  {'perturbation':26s} {'tested':>8s} {'false +':>8s} {'rate':>8s}")
    for n, d in r["equivalence"].items():
        rate = f"{d['false_positives']/d['tested']:8.3f}" if d["tested"] else "     n/a"
        print(f"  {n:26s} {d['tested']:8d} {d['false_positives']:8d} {rate}")
        for ex in d["examples"]:
            print(f"      {ex['study']}: paper={ex['paper']} repo={ex['repo']}")

    if any(r["collateral"].values()):
        print("\nCOLLATERAL (conflicts of OTHER types raised by one injection)")
        for t, n in r["collateral"].items():
            print(f"  planting {t}: {n} unrelated conflict(s)")
    else:
        print("\nCOLLATERAL: none — an injection never raised an unrelated type.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    r = evaluate(a.model)
    report(r)
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=2))
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
