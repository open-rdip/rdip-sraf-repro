#!/usr/bin/env python3
"""
Extraction precision / recall / F1 against a human gold standard (RQ3).

Compares each model's extracted metadata (the JSON the pipeline writes to
data/extractions/<study>__<model_slug>.json) against hand-annotated gold files
(evaluation/gold_standard/<study>.json), per field, and reports precision,
recall and F1 — micro-averaged across studies (per field and overall) and
macro-averaged (mean of per-study F1).

Two matching strictnesses:
  • lenient  — item present by its identifying key (e.g. dependency NAME,
               hyperparameter NAME, eval (metric, split)).
  • strict   — key PLUS the value (dependency name+version, hyperparam
               name+value, eval metric+value+split). Quantifies how often the
               model also gets the value right, not just the field.

Usage:
    python evaluation/eval_extraction.py --model <model_slug> [--strict]
                                         [--extractions data/extractions]
                                         [--gold evaluation/gold_standard]
                                         [--json out.json]

Gold and prediction share the pipeline's `metadata` schema (see
evaluation/gold_schema.md).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import defaultdict


# ── Normalisation ─────────────────────────────────────────────────────────────

def _s(x) -> str:
    return (str(x) if x is not None else "").strip().lower()


def _canon_value(x) -> str:
    """Canonicalise a reported value so '0.94', '0.940', '94%' compare sanely.
    Percent → fraction; numbers → trimmed float; else lowercased string."""
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


# ── Field key functions (identity of an extracted item) ───────────────────────
# lenient = how we decide two items are "the same thing"; strict adds the value.

LENIENT = {
    "dependencies":       lambda d: _s(d.get("name")),
    "random_seeds":       lambda s: _s(s),
    "hyperparameters":    lambda h: _s(h.get("name")),
    "datasets":           lambda d: _s(d.get("name")),
    "methods":            lambda m: _s(m.get("name")),
    "evaluation_results": lambda e: (_s(e.get("metric")), _s(e.get("split"))),
}

STRICT = {
    "dependencies":       lambda d: (_s(d.get("name")), _s(d.get("version"))),
    "random_seeds":       lambda s: _s(s),
    "hyperparameters":    lambda h: (_s(h.get("name")), _canon_value(h.get("value"))),
    "datasets":           lambda d: (_s(d.get("name")), _s(d.get("version"))),
    "methods":            lambda m: _s(m.get("name")),
    "evaluation_results": lambda e: (_s(e.get("metric")), _canon_value(e.get("value")),
                                     _s(e.get("split"))),
}

HARDWARE_FIELDS = ("gpu_model", "cuda_version", "cpu_info")
FIELDS = list(LENIENT.keys()) + ["hardware"]


# ── Core metrics (pure) ───────────────────────────────────────────────────────

def prf(tp: int, fp: int, fn: int) -> dict:
    """Precision / recall / F1 from counts (0 when undefined)."""
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def list_counts(gold_items, pred_items, key_fn) -> tuple[int, int, int]:
    """TP/FP/FN for one list-valued field via set matching on the key."""
    g = {key_fn(i) for i in (gold_items or []) if key_fn(i) not in ("", (), None)}
    p = {key_fn(i) for i in (pred_items or []) if key_fn(i) not in ("", (), None)}
    tp = len(g & p)
    return tp, len(p - g), len(g - p)


def hardware_counts(gold_hw: dict, pred_hw: dict) -> tuple[int, int, int]:
    """TP/FP/FN over the three scalar hardware slots."""
    gold_hw, pred_hw = gold_hw or {}, pred_hw or {}
    tp = fp = fn = 0
    for f in HARDWARE_FIELDS:
        g, p = _s(gold_hw.get(f)), _s(pred_hw.get(f))
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
    """Per-field TP/FP/FN for one study (gold vs pred `metadata` dicts)."""
    keys = STRICT if strict else LENIENT
    out: dict[str, tuple[int, int, int]] = {}
    for field, key_fn in keys.items():
        out[field] = list_counts(gold.get(field), pred.get(field), key_fn)
    out["hardware"] = hardware_counts(gold.get("hardware"), pred.get("hardware"))
    return out


def aggregate(per_study: dict[str, dict]) -> dict:
    """Micro (per field + overall) and macro F1 from per-study counts.

    per_study: {study_id: {field: (tp, fp, fn)}}
    """
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

    micro = {f: prf(*field_tot[f]) for f in FIELDS}
    micro_overall = prf(*overall)
    macro_f1 = round(sum(study_f1) / len(study_f1), 3) if study_f1 else 0.0
    return {
        "n_studies": len(per_study),
        "per_field_micro": micro,
        "overall_micro": micro_overall,
        "macro_f1": macro_f1,
    }


# ── I/O + driver ──────────────────────────────────────────────────────────────

def _metadata(doc: dict) -> dict:
    """Both gold and prediction store the fields under `metadata`; tolerate a
    flat file too."""
    return doc.get("metadata", doc)


def load_pairs(model_slug: str, extractions_dir: str, gold_dir: str
               ) -> tuple[dict, list]:
    """Return ({study: counts-source pair}, skipped) for studies with BOTH a
    gold file and this model's extraction."""
    pairs, skipped = {}, []
    for gold_path in sorted(glob.glob(os.path.join(gold_dir, "*.json"))):
        study = os.path.splitext(os.path.basename(gold_path))[0]
        if study.endswith(".template"):
            continue
        pred_path = os.path.join(extractions_dir, f"{study}__{model_slug}.json")
        if not os.path.exists(pred_path):
            skipped.append({"study": study, "reason": "no extraction for model"})
            continue
        gold = _metadata(json.load(open(gold_path)))
        pred = _metadata(json.load(open(pred_path)))
        pairs[study] = (gold, pred)
    return pairs, skipped


def run(model_slug: str, extractions_dir: str, gold_dir: str,
        strict: bool = False) -> dict:
    pairs, skipped = load_pairs(model_slug, extractions_dir, gold_dir)
    per_study = {s: evaluate_study(g, p, strict) for s, (g, p) in pairs.items()}
    report = aggregate(per_study)
    report.update({"model": model_slug, "strict": strict, "skipped": skipped})
    return report


def print_report(rep: dict) -> None:
    mode = "strict" if rep["strict"] else "lenient"
    print(f"\n=== extraction eval — model={rep['model']} ({mode}) — "
          f"{rep['n_studies']} studies ===")
    print(f"  {'field':20s} {'P':>6} {'R':>6} {'F1':>6}   (tp/fp/fn)")
    for f, m in rep["per_field_micro"].items():
        print(f"  {f:20s} {m['precision']:6.3f} {m['recall']:6.3f} {m['f1']:6.3f}   "
              f"({m['tp']}/{m['fp']}/{m['fn']})")
    o = rep["overall_micro"]
    print(f"  {'OVERALL (micro)':20s} {o['precision']:6.3f} {o['recall']:6.3f} "
          f"{o['f1']:6.3f}   ({o['tp']}/{o['fp']}/{o['fn']})")
    print(f"  {'macro F1 (per-study mean)':30s} {rep['macro_f1']:.3f}")
    if rep["skipped"]:
        print(f"  skipped {len(rep['skipped'])} study(ies) with no extraction "
              f"for this model")


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="model slug (matches the "
                    "data/extractions/<study>__<slug>.json filenames)")
    ap.add_argument("--extractions", default=os.path.join(root, "data", "extractions"))
    ap.add_argument("--gold", default=os.path.join(here, "gold_standard"))
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    rep = run(args.model, args.extractions, args.gold, strict=args.strict)
    print_report(rep)
    if args.json:
        json.dump(rep, open(args.json, "w"), indent=2)
        print(f"\n[eval] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
