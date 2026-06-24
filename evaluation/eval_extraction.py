#!/usr/bin/env python3
"""
Extraction precision / recall / F1 against the human ground truth (RQ3).

SCOPE: SRAF's instrument uses *reproducibility* metadata, so RQ3 evaluates the
LLM paper-extraction on the reproducibility fields only. Fields are grouped:

  PAPER-DERIVABLE (headline)  : methods, parameters, datasets,
                                evaluation_results, environment
  REPO-DERIVED (asymmetry)    : software, random_seeds
    — the ground truth drew these from the repo (requirements.txt, code seeds),
      which the paper-only LLM never saw; SRAF supplies them deterministically
      in Phase I. Reported separately, not in the headline.

Matching has two independent axes:
  • value strictness : lenient (item found) vs strict (--strict: + value)
  • name matching    : exact vs fuzzy (--match)
      fuzzy = normalised + acronym-aware + token-overlap, so a model that
      outputs 'RTN' is credited against gold 'Round-to-nearest (RTN)', and
      'CIFAR10' against 'CIFAR-10'. Report BOTH for a defensible range.

A field whose gold side is empty across all studies is marked N/A (e.g. seeds
on the 12 gold papers, which contain none).

    python -m evaluation.eval_extraction --model <slug> [--tier gold|silver]
                                         [--match exact|fuzzy] [--strict]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re


# ── Normalisation helpers ─────────────────────────────────────────────────────

_NULLISH = {"", "null", "none", "n/a", "na", "nan", "nil", "unknown",
            "not specified", "exact version not specified", "not reported",
            "not stated", "modern gpus"}

_STOP = {"the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "with",
         "via", "using", "based", "our", "their"}


def _s(x) -> str:
    return (str(x) if x is not None else "").strip().lower()


def _clean(v):
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


def _norm(s) -> str:
    """Lowercase, drop parentheticals, strip punctuation, collapse whitespace."""
    s = _s(s)
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s) -> list[str]:
    return [t for t in _norm(s).split() if t not in _STOP and len(t) > 1]


def _acronyms(s) -> set[str]:
    out = set()
    for m in re.findall(r"\(([A-Za-z0-9\-]{2,})\)", s or ""):   # parenthetical
        out.add(re.sub(r"[^a-z0-9]", "", m.lower()))
    toks = _tokens(s)
    if len(toks) >= 2:
        out.add("".join(t[0] for t in toks))                    # initials
    return out


def names_match(a, b) -> bool:
    """Entity-aware fuzzy name equality (normalised + acronym + token overlap)."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # acronym: one side's normalised string equals the other's acronym
    aca, acb = _acronyms(a), _acronyms(b)
    if na.replace(" ", "") in acb or nb.replace(" ", "") in aca:
        return True
    if aca & acb:
        return True
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if ta and tb:
        if len(ta & tb) / len(ta | tb) >= 0.5:                  # Jaccard
            return True
    sa, sb = na.replace(" ", ""), nb.replace(" ", "")
    short, long = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    if len(short) >= 4 and short in long:                       # containment
        return True
    return False


# ── Adapters: both sides → common reproducibility-field shape ──────────────────

def _named(items, get):
    return [i for i in (items or []) if _clean(get(i)) is not None]


def normalize_gold(doc: dict) -> dict:
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


# ── Field model: (name, exact-extra, value) per item ──────────────────────────

LIST_FIELDS = ["software", "datasets", "methods", "parameters",
               "random_seeds", "evaluation_results"]
FIELDS = LIST_FIELDS + ["environment"]
PAPER_FIELDS = ["methods", "parameters", "datasets", "evaluation_results", "environment"]
REPO_FIELDS = ["software", "random_seeds"]


def _triple(field: str, item):
    """(name, exact_extra, value) for an item — extra must match exactly."""
    if field == "software":
        return item.get("name"), "", item.get("version")
    if field in ("datasets", "methods"):
        return item.get("name"), "", None
    if field == "parameters":
        return item.get("name"), "", item.get("value")
    if field == "random_seeds":
        return item, "", None                      # item is the value string
    if field == "evaluation_results":
        # identity = metric + reported value (split is unreliable: models often
        # omit it while gold says 'test', so it is NOT a hard constraint).
        return item.get("metric"), "", item.get("value")
    raise KeyError(field)


# evaluation results are only "the same" if the reported VALUE also matches, so
# value is part of identity even in lenient mode.
_VALUE_IN_LENIENT = {"evaluation_results"}


# ── Core metrics ──────────────────────────────────────────────────────────────

def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def field_counts(field, gold_items, pred_items, strict, fuzzy) -> tuple[int, int, int]:
    """Greedy one-to-one matching. name: exact (_s) or fuzzy; extra (split):
    exact; value (strict only): canonicalised."""
    gold = [_triple(field, i) for i in (gold_items or [])]
    pred = [_triple(field, i) for i in (pred_items or [])]
    gold = [g for g in gold if _clean(g[0]) is not None and _s(g[0])]
    pred = [p for p in pred if _clean(p[0]) is not None and _s(p[0])]
    need_value = strict or field in _VALUE_IN_LENIENT
    used = [False] * len(pred)
    tp = 0
    for gn, ge, gv in gold:
        for j, (pn, pe, pv) in enumerate(pred):
            if used[j] or _s(ge) != _s(pe):
                continue
            nm = names_match(gn, pn) if fuzzy else (_s(gn) == _s(pn))
            if not nm:
                continue
            if need_value and _canon_value(gv) != _canon_value(pv):
                continue
            used[j] = True
            tp += 1
            break
    return tp, used.count(False), len(gold) - tp


def scalar_counts(gold, pred, slots, fuzzy) -> tuple[int, int, int]:
    gold, pred = gold or {}, pred or {}
    tp = fp = fn = 0
    for s in slots:
        g, p = gold.get(s), pred.get(s)
        gs, ps = _s(g), _s(p)
        if gs and ps:
            ok = names_match(g, p) if fuzzy else (gs == ps)
            tp += 1 if ok else 0
            fp += 0 if ok else 1
            fn += 0 if ok else 1
        elif ps and not gs:
            fp += 1
        elif gs and not ps:
            fn += 1
    return tp, fp, fn


def evaluate_study(gold, pred, strict=False, fuzzy=False) -> dict:
    out = {f: field_counts(f, gold.get(f), pred.get(f), strict, fuzzy)
           for f in LIST_FIELDS}
    out["environment"] = scalar_counts(gold.get("environment"),
                                       pred.get("environment"),
                                       ("gpu_model", "cuda_version"), fuzzy)
    return out


def _micro(per_study, fields) -> dict:
    tot = [0, 0, 0]
    for c in per_study.values():
        for f in fields:
            tot[0] += c[f][0]; tot[1] += c[f][1]; tot[2] += c[f][2]
    return prf(*tot)


def aggregate(per_study: dict[str, dict]) -> dict:
    field = {}
    for f in FIELDS:
        tot = [0, 0, 0]
        for c in per_study.values():
            tot[0] += c[f][0]; tot[1] += c[f][1]; tot[2] += c[f][2]
        m = prf(*tot)
        m["support"] = tot[0] + tot[2]            # gold positives (tp + fn)
        m["na"] = (m["support"] == 0)
        field[f] = m
    macro = []
    for c in per_study.values():
        t = [0, 0, 0]
        for f in PAPER_FIELDS:
            t[0] += c[f][0]; t[1] += c[f][1]; t[2] += c[f][2]
        macro.append(prf(*t)["f1"])
    return {
        "n_studies": len(per_study),
        "per_field": field,
        "headline_micro": _micro(per_study, PAPER_FIELDS),   # paper-derivable
        "repo_micro": _micro(per_study, REPO_FIELDS),        # asymmetric
        "overall_micro": _micro(per_study, FIELDS),
        "macro_f1": round(sum(macro) / len(macro), 3) if macro else 0.0,
    }


# ── I/O + driver ──────────────────────────────────────────────────────────────

def load_pairs(model_slug, extractions_dir, gt_dir, tier):
    pairs, skipped = {}, []
    for sdir in sorted(glob.glob(os.path.join(gt_dir, tier, "study*"))):
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


def run(model_slug, extractions_dir, gt_dir, tier="gold", strict=False, fuzzy=False):
    pairs, skipped = load_pairs(model_slug, extractions_dir, gt_dir, tier)
    per_study = {s: evaluate_study(g, p, strict, fuzzy) for s, (g, p) in pairs.items()}
    rep = aggregate(per_study)
    rep.update({"model": model_slug, "tier": tier, "strict": strict,
                "fuzzy": fuzzy, "skipped": skipped})
    return rep


def _f1cell(m):
    return "  n/a " if m["na"] else f"{m['f1']:6.3f}"


def print_report(rep):
    mode = ("strict" if rep["strict"] else "lenient") + \
           ("/fuzzy" if rep["fuzzy"] else "/exact")
    print(f"\n=== RQ3 — model={rep['model']} tier={rep['tier']} ({mode}) — "
          f"{rep['n_studies']} studies ===")
    print(f"  {'field':20s} {'P':>6} {'R':>6} {'F1':>6}  (tp/fp/fn)")
    for f in PAPER_FIELDS + REPO_FIELDS:
        m = rep["per_field"][f]
        tag = "  [repo]" if f in REPO_FIELDS else ""
        print(f"  {f:20s} {m['precision']:6.3f} {m['recall']:6.3f} {_f1cell(m)}  "
              f"({m['tp']}/{m['fp']}/{m['fn']}){tag}")
    h, o = rep["headline_micro"], rep["overall_micro"]
    print(f"  {'HEADLINE (paper)':20s} {h['precision']:6.3f} {h['recall']:6.3f} "
          f"{h['f1']:6.3f}")
    print(f"  {'overall (all)':20s} {o['precision']:6.3f} {o['recall']:6.3f} "
          f"{o['f1']:6.3f}")
    print(f"  macro F1 (paper, per-study mean): {rep['macro_f1']:.3f}")


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--tier", default="gold", choices=["gold", "silver"])
    ap.add_argument("--match", default="exact", choices=["exact", "fuzzy"])
    ap.add_argument("--extractions", default=os.path.join(root, "data", "extractions"))
    ap.add_argument("--ground-truth", default=os.path.join(root, "data", "ground_truth"))
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    rep = run(args.model, args.extractions, args.ground_truth, args.tier,
              args.strict, fuzzy=(args.match == "fuzzy"))
    print_report(rep)
    if args.json:
        json.dump(rep, open(args.json, "w"), indent=2)
        print(f"\n[eval] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
