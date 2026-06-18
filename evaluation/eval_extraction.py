#!/usr/bin/env python3
"""
Extraction precision / recall / F1 against the human ground truth (RQ3).

SCOPE: SRAF's instrument uses *reproducibility* metadata, so RQ3 evaluates the
LLM paper-extraction on the seven reproducibility fields only — software,
datasets, methods, parameters, random seeds, environment, evaluation results.
The ground truth's richer RDIP entities (Person / Organization / Activity /
relations) are out of scope here and are mapped away.

Both sides are normalised to a common shape before scoring:
  • ground truth  data/ground_truth/<tier>/<study>/gold_standard.json
                  (RDIP entities: SoftwareApplication, Dataset, Method,
                   Parameter, RandomSeed, ComputingEnvironment, EvaluationResult)
  • prediction    data/extractions/<study>__<model_slug>.json  (pipeline output)

Two strictnesses: lenient (item found by its identifying key) and strict (key +
value). Reports micro P/R/F1 per field + overall, and macro F1 (mean per-study).

    python evaluation/eval_extraction.py --model <slug> [--tier gold|silver]
                                         [--strict] [--json out.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from itertools import combinations  # noqa: F401  (kept for parity/testing)


# ── Normalisation helpers ─────────────────────────────────────────────────────

_NULLISH = {"", "null", "none", "n/a", "na", "nan", "nil", "unknown",
            "not specified", "exact version not specified", "not reported",
            "not stated", "modern gpus"}


def _s(x) -> str:
    return (str(x) if x is not None else "").strip().lower()


def _clean(v):
    """Coerce nullish strings (incl. gold's 'exact version not specified') to None."""
    if isinstance(v, str) and v.strip().lower() in _NULLISH:
        return None
    return v


def _canon_value(x) -> str:
    """'0.94', '0.940', '94%' → same canonical token; else lowercased string."""
    s = _s(x)
    if not s:
        return ""
    pct = s.endswith("%")
    num = s[:-1] if pct else s
    try:
        v = float(num)
        if pct:
            v /= 100.0
        return f"{v:.6g}"
    except ValueError:
        return s


# ── Adapters: both sides → common reproducibility-field shape ──────────────────

def _named(items, name_getter):
    """Keep only items whose name is non-nullish (robust to either side emitting
    the literal 'null'/'n/a')."""
    return [i for i in (items or []) if _clean(name_getter(i)) is not None]


def normalize_gold(doc: dict) -> dict:
    """RDIP ground-truth entities → the seven reproducibility fields."""
    e = doc.get("entities", {}) or {}
    env_list = e.get("ComputingEnvironment") or []
    env0 = env_list[0] if env_list else {}
    _n = lambda x: x.get("name")
    return {
        "software": [{"name": s.get("name"), "version": _clean(s.get("version"))}
                     for s in _named(e.get("SoftwareApplication"), _n)],
        "datasets": [{"name": d.get("name")} for d in _named(e.get("Dataset"), _n)],
        "methods":  [{"name": m.get("name")} for m in _named(e.get("Method"), _n)],
        "parameters": [{"name": p.get("name"), "value": _clean(p.get("value"))}
                       for p in _named(e.get("Parameter"), _n)],
        "random_seeds": [_s(s.get("value")) for s in e.get("RandomSeed", [])
                         if _clean(s.get("value")) is not None],
        "environment": {"gpu_model": _clean(env0.get("gpu")),
                        "cuda_version": _clean(env0.get("cuda"))},
        "evaluation_results": [{"metric": r.get("metric"), "value": _clean(r.get("value")),
                                "split": r.get("split")}
                               for r in e.get("EvaluationResult", [])],
    }


def normalize_pred(doc: dict) -> dict:
    """Pipeline extraction `metadata` → the seven reproducibility fields."""
    md = doc.get("metadata", doc) or {}
    hw = md.get("hardware") or {}
    _n = lambda x: x.get("name")
    _nm = lambda m: (m.get("name") if isinstance(m, dict) else m)
    return {
        "software": [{"name": d.get("name"), "version": _clean(d.get("version"))}
                     for d in _named(md.get("dependencies"), _n)],
        "datasets": [{"name": d.get("name")} for d in _named(md.get("datasets"), _n)],
        "methods":  [{"name": _nm(m)}
                     for m in (md.get("methods") or []) if _clean(_nm(m)) is not None],
        "parameters": [{"name": p.get("name"), "value": _clean(p.get("value"))}
                       for p in _named(md.get("hyperparameters"), _n)],
        "random_seeds": [_s(s) for s in md.get("random_seeds", [])],
        "environment": {"gpu_model": _clean(hw.get("gpu_model")),
                        "cuda_version": _clean(hw.get("cuda_version"))},
        "evaluation_results": [{"metric": r.get("metric"), "value": _clean(r.get("value")),
                                "split": r.get("split")}
                               for r in md.get("evaluation_results", [])],
    }


# ── Field keys (item identity) ────────────────────────────────────────────────

LENIENT = {
    "software":           lambda x: _s(x.get("name")),
    "datasets":           lambda x: _s(x.get("name")),
    "methods":            lambda x: _s(x.get("name")),
    "parameters":         lambda x: _s(x.get("name")),
    "random_seeds":       lambda x: _s(x),
    "evaluation_results": lambda x: (_s(x.get("metric")), _s(x.get("split"))),
}
STRICT = {
    "software":           lambda x: (_s(x.get("name")), _s(x.get("version"))),
    "datasets":           lambda x: _s(x.get("name")),
    "methods":            lambda x: _s(x.get("name")),
    "parameters":         lambda x: (_s(x.get("name")), _canon_value(x.get("value"))),
    "random_seeds":       lambda x: _s(x),
    "evaluation_results": lambda x: (_s(x.get("metric")), _canon_value(x.get("value")),
                                     _s(x.get("split"))),
}
LIST_FIELDS = list(LENIENT.keys())
ENV_SLOTS = ("gpu_model", "cuda_version")
FIELDS = LIST_FIELDS + ["environment"]


# ── Core metrics (pure) ───────────────────────────────────────────────────────

def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def list_counts(gold_items, pred_items, key_fn) -> tuple[int, int, int]:
    g = {key_fn(i) for i in (gold_items or []) if key_fn(i) not in ("", (), None)}
    p = {key_fn(i) for i in (pred_items or []) if key_fn(i) not in ("", (), None)}
    return len(g & p), len(p - g), len(g - p)


def scalar_counts(gold: dict, pred: dict, slots) -> tuple[int, int, int]:
    """TP/FP/FN over a fixed set of scalar slots (e.g. environment)."""
    gold, pred = gold or {}, pred or {}
    tp = fp = fn = 0
    for s in slots:
        g, p = _s(gold.get(s)), _s(pred.get(s))
        if g and p:
            tp += 1 if g == p else 0
            fp += 0 if g == p else 1
            fn += 0 if g == p else 1
        elif p and not g:
            fp += 1
        elif g and not p:
            fn += 1
    return tp, fp, fn


def evaluate_study(gold: dict, pred: dict, strict: bool = False) -> dict:
    keys = STRICT if strict else LENIENT
    out = {f: list_counts(gold.get(f), pred.get(f), keys[f]) for f in LIST_FIELDS}
    out["environment"] = scalar_counts(gold.get("environment"),
                                       pred.get("environment"), ENV_SLOTS)
    return out


def aggregate(per_study: dict[str, dict]) -> dict:
    field_tot = {f: [0, 0, 0] for f in FIELDS}
    overall = [0, 0, 0]
    study_f1 = []
    for counts in per_study.values():
        s_tp = s_fp = s_fn = 0
        for f in FIELDS:
            tp, fp, fn = counts[f]
            field_tot[f][0] += tp; field_tot[f][1] += fp; field_tot[f][2] += fn
            s_tp += tp; s_fp += fp; s_fn += fn
        overall[0] += s_tp; overall[1] += s_fp; overall[2] += s_fn
        study_f1.append(prf(s_tp, s_fp, s_fn)["f1"])
    return {
        "n_studies": len(per_study),
        "per_field_micro": {f: prf(*field_tot[f]) for f in FIELDS},
        "overall_micro": prf(*overall),
        "macro_f1": round(sum(study_f1) / len(study_f1), 3) if study_f1 else 0.0,
    }


# ── I/O + driver ──────────────────────────────────────────────────────────────

def load_pairs(model_slug: str, extractions_dir: str, gt_dir: str, tier: str
               ) -> tuple[dict, list]:
    """{study: (gold_fields, pred_fields)} for studies with BOTH a ground-truth
    file (this tier) and this model's extraction."""
    pairs, skipped = {}, []
    tier_dir = os.path.join(gt_dir, tier)
    for sdir in sorted(glob.glob(os.path.join(tier_dir, "study*"))):
        study = os.path.basename(sdir)
        gpath = os.path.join(sdir, "gold_standard.json")
        ppath = os.path.join(extractions_dir, f"{study}__{model_slug}.json")
        if not os.path.exists(gpath):
            continue
        if not os.path.exists(ppath):
            skipped.append({"study": study, "reason": "no extraction for model"})
            continue
        pairs[study] = (normalize_gold(json.load(open(gpath))),
                        normalize_pred(json.load(open(ppath))))
    return pairs, skipped


def run(model_slug: str, extractions_dir: str, gt_dir: str,
        tier: str = "gold", strict: bool = False) -> dict:
    pairs, skipped = load_pairs(model_slug, extractions_dir, gt_dir, tier)
    per_study = {s: evaluate_study(g, p, strict) for s, (g, p) in pairs.items()}
    rep = aggregate(per_study)
    rep.update({"model": model_slug, "tier": tier, "strict": strict,
                "skipped": skipped})
    return rep


def print_report(rep: dict) -> None:
    mode = "strict" if rep["strict"] else "lenient"
    print(f"\n=== RQ3 extraction eval — model={rep['model']} — tier={rep['tier']} "
          f"({mode}) — {rep['n_studies']} studies ===")
    print(f"  {'field':20s} {'P':>6} {'R':>6} {'F1':>6}   (tp/fp/fn)")
    for f, m in rep["per_field_micro"].items():
        print(f"  {f:20s} {m['precision']:6.3f} {m['recall']:6.3f} {m['f1']:6.3f}   "
              f"({m['tp']}/{m['fp']}/{m['fn']})")
    o = rep["overall_micro"]
    print(f"  {'OVERALL (micro)':20s} {o['precision']:6.3f} {o['recall']:6.3f} "
          f"{o['f1']:6.3f}   ({o['tp']}/{o['fp']}/{o['fn']})")
    print(f"  macro F1 (per-study mean): {rep['macro_f1']:.3f}")
    if rep["skipped"]:
        print(f"  skipped {len(rep['skipped'])} study(ies) with no extraction "
              f"for this model")


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True,
                    help="model slug (matches data/extractions/<study>__<slug>.json)")
    ap.add_argument("--tier", default="gold", choices=["gold", "silver"])
    ap.add_argument("--extractions", default=os.path.join(root, "data", "extractions"))
    ap.add_argument("--ground-truth", default=os.path.join(root, "data", "ground_truth"))
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    rep = run(args.model, args.extractions, args.ground_truth, args.tier, args.strict)
    print_report(rep)
    if args.json:
        json.dump(rep, open(args.json, "w"), indent=2)
        print(f"\n[eval] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
