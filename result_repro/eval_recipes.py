"""Evaluate the engine-extracted execution recipes against a human-verified gold set.

This is the recipe analogue of the RQ3 extraction benchmark: it measures how well
the engine derives "how to reproduce" on its own. The run harness uses the
*extracted* recipe; the gold set is used ONLY to score the extraction.

  data/recipes/<study>.json          : engine output (from extract_recipes.py)
  result_repro/gold_recipes/<study>.json : human-verified reference

Metrics per study (only for studies with both files):
  has_command       : engine produced a non-null run_command
  entry_point_hit   : extracted command references the gold entry-point file
  command_jaccard   : token overlap of extracted vs gold run_command
  dataset_f1        : requires_dataset name match (fuzzy)
  metric_f1         : produces_metric name match (fuzzy)

  ~/envs/sraf/bin/python -m result_repro.eval_recipes
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, ROOT)
from evaluation.eval_extraction import names_match, _s  # noqa: E402

RECIPES_DIR = os.path.join(ROOT, "data", "recipes")
GOLD_DIR = os.path.join(ROOT, "result_repro", "gold_recipes")


def _tokens(cmd) -> set:
    return set(re.findall(r"[A-Za-z0-9_./-]+", _s(cmd).lower()))


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 1.0


def _name_f1(pred_names, gold_names) -> float:
    pred = [n for n in pred_names if n]
    gold = [n for n in gold_names if n]
    if not gold and not pred:
        return 1.0
    if not gold or not pred:
        return 0.0
    tp = sum(any(names_match(p, g) for p in pred) for g in gold)
    prec = sum(any(names_match(p, g) for g in gold) for p in pred) / len(pred)
    rec = tp / len(gold)
    return round(2 * prec * rec / (prec + rec), 3) if (prec + rec) else 0.0


def _names(items, key):
    out = []
    for x in items or []:
        out.append(x.get(key) if isinstance(x, dict) else x)
    return out


def evaluate_one(pred: dict, gold: dict) -> dict:
    gcmd, pcmd = gold.get("run_command"), pred.get("run_command")
    entry = _s(gold.get("entry_point"))
    return {
        "has_command": bool(pcmd),
        "entry_point_hit": bool(entry and entry.lower() in _s(pcmd).lower()),
        "command_jaccard": round(_jaccard(_tokens(pcmd), _tokens(gcmd)), 3),
        "dataset_f1": _name_f1(_names(pred.get("requires_dataset"), "name"),
                               _names(gold.get("requires_dataset"), "name")),
        "metric_f1": _name_f1(_names(pred.get("produces_metric"), "metric"),
                              _names(gold.get("produces_metric"), "metric")),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recipes", default=RECIPES_DIR)
    ap.add_argument("--gold", default=GOLD_DIR)
    a = ap.parse_args()

    rows, agg = [], {"has_command": 0, "entry_point_hit": 0,
                     "command_jaccard": 0.0, "dataset_f1": 0.0, "metric_f1": 0.0}
    for gp in sorted(glob.glob(os.path.join(a.gold, "*.json"))):
        study = os.path.splitext(os.path.basename(gp))[0]
        pp = os.path.join(a.recipes, f"{study}.json")
        if not os.path.isfile(pp):
            print(f"  {study}: no extracted recipe — skip")
            continue
        r = evaluate_one(json.load(open(pp)), json.load(open(gp)))
        r["study_id"] = study
        rows.append(r)
        for k in agg:
            agg[k] += r[k]

    n = len(rows)
    print(f"\n=== Recipe-extraction quality ({n} studies with gold) ===")
    if n:
        print(f"  has command        : {agg['has_command']}/{n} "
              f"({agg['has_command']/n:.0%})")
        print(f"  entry-point hit    : {agg['entry_point_hit']}/{n} "
              f"({agg['entry_point_hit']/n:.0%})")
        print(f"  command Jaccard    : {agg['command_jaccard']/n:.3f}")
        print(f"  dataset F1         : {agg['dataset_f1']/n:.3f}")
        print(f"  metric F1          : {agg['metric_f1']/n:.3f}")
        print()
        for r in rows:
            print(f"  {r['study_id']:9s} cmd={int(r['has_command'])} "
                  f"entry={int(r['entry_point_hit'])} "
                  f"jac={r['command_jaccard']:.2f} "
                  f"ds_f1={r['dataset_f1']:.2f} m_f1={r['metric_f1']:.2f}")
    else:
        print("  no (extracted, gold) pairs found — add gold recipes in "
              f"{a.gold}/ (see the template).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
