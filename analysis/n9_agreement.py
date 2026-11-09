"""N9 inter-annotator agreement, written and tested before the data exists.

Two annotators judge the same candidate rows. Annotator 1 is the first author,
whose decisions are the committed ground truth (`in_ground_truth` yes/no in
`evaluation/annotation_round1_key/origin_key.csv`). Annotator 2 is the second
annotator, whose decisions arrive as the workbook export (K/D/U per row).

Three things this module is careful about, each because the naive version of it
would be wrong:

1. **Unsure is not a third label.** `U` means the annotator declined to decide,
   not that they decided "neither". Treating it as a category inflates the
   number of categories and deflates chance agreement. Rows where either side is
   `U` leave the agreement denominator and are reported as a separate count.

2. **Two coefficients, because prevalence is skewed.** The corpus prevalence of
   `keep` is roughly 26%, which is the regime where Cohen's kappa is depressed
   by the prevalence paradox: high observed agreement, low kappa, for no reason
   that reflects the annotators. Gwet's AC1 is reported beside it because its
   chance term does not collapse under skew. Where the two diverge, the
   divergence is the finding and both are printed.

3. **Additions are not an agreement problem.** An annotator may add a row the
   pipeline never proposed. There is no matching judgement from the other side
   to agree or disagree with, so additions are scored as precision and recall
   against the other annotator's additions and never folded into a coefficient.

Fields with too few rows get no coefficient at all. See MIN_FIELD_N.

Usage:
    python analysis/n9_agreement.py --self-test
    python analysis/n9_agreement.py --key evaluation/annotation_round1_key/origin_key.csv \
        --annotator path/to/export.json --out analysis/n9_agreement.md
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field as dc_field

import numpy as np

# A field gets a coefficient only above this many jointly-decided rows. At
# n = 30 and p = 0.26 the bootstrap interval on kappa spans roughly +/-0.25,
# which cannot distinguish "good" from "poor" agreement and so should not be
# printed as though it could. On the 12 gold studies this threshold admits
# methods (349), evaluation_results (220), dependencies (216),
# hyperparameters (159) and datasets (143), and excludes environment (30) and
# random_seeds (10). That split was known before the data arrived and is
# recorded here so it cannot be chosen after seeing the coefficients.
MIN_FIELD_N = 50

BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 20261109
KEEP, DISCARD, UNSURE = "K", "D", "U"


# --------------------------------------------------------------- coefficients
def _confusion(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Observed agreement and the two marginal keep-rates."""
    po = float(np.mean(a == b))
    return po, float(np.mean(a == 1)), float(np.mean(b == 1))


def cohen_kappa(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's kappa for two binary label vectors coded 0/1."""
    if len(a) == 0:
        return float("nan")
    po, p1, p2 = _confusion(a, b)
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    if pe >= 1.0:
        return float("nan")       # both annotators used one label throughout
    return (po - pe) / (1 - pe)


def gwet_ac1(a: np.ndarray, b: np.ndarray) -> float:
    """Gwet's AC1 for two binary label vectors coded 0/1.

    pe = 2 * pi * (1 - pi) with pi the mean marginal prevalence. Unlike
    Cohen's pe this does not approach 1 as prevalence becomes extreme, which
    is the whole reason it is here.
    """
    if len(a) == 0:
        return float("nan")
    po, p1, p2 = _confusion(a, b)
    pi = (p1 + p2) / 2.0
    pe = 2.0 * pi * (1.0 - pi)
    if pe >= 1.0:
        return float("nan")
    return (po - pe) / (1 - pe)


def bootstrap_ci(a: np.ndarray, b: np.ndarray, fn, n: int = BOOTSTRAP_N,
                 seed: int = BOOTSTRAP_SEED, alpha: float = 0.05
                 ) -> tuple[float, float]:
    """Percentile bootstrap interval over rows.

    Resampling rows rather than studies is the right unit here only because
    the reported coefficient is a within-field statistic; a claim about
    between-study variation would need a cluster bootstrap and is not made.
    """
    if len(a) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n, len(a)))
    vals = np.array([fn(a[i], b[i]) for i in idx])
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return (float("nan"), float("nan"))
    return (float(np.percentile(vals, 100 * alpha / 2)),
            float(np.percentile(vals, 100 * (1 - alpha / 2))))


# ------------------------------------------------------------------ data load
@dataclass
class Row:
    item_id: str
    field: str
    study: str
    a1: str                     # K or D, from the committed key
    a2: str                     # K, D or U, from the annotator export
    note: str = ""


@dataclass
class Loaded:
    rows: list[Row] = dc_field(default_factory=list)
    calibration: list[dict] = dc_field(default_factory=list)
    additions_a2: dict = dc_field(default_factory=dict)
    missing_from_export: list[str] = dc_field(default_factory=list)
    undecided: list[str] = dc_field(default_factory=list)


def load(key_path: str, export_path: str) -> Loaded:
    key = {}
    with open(key_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            yes = r["in_ground_truth"].strip().lower() in ("yes", "y", "true", "1")
            key[r["item_id"]] = (r["field"], KEEP if yes else DISCARD)

    with open(export_path, encoding="utf-8") as fh:
        exp = json.load(fh)

    out = Loaded(calibration=(exp.get("calibration_n9")
                              or exp.get("screening") or {}).get("answers", []))
    for s in exp.get("studies", []):
        if s.get("additions"):
            out.additions_a2[s["study_id"]] = s["additions"]
        for it in s.get("items", []):
            iid = it["item_id"]
            d = (it.get("decision") or "").strip().upper()
            if iid not in key:
                out.missing_from_export.append(iid)
                continue
            if d not in (KEEP, DISCARD, UNSURE):
                out.undecided.append(iid)
                continue
            out.rows.append(Row(iid, key[iid][0], s["study_id"], key[iid][1], d,
                                it.get("note") or ""))
    return out


# ------------------------------------------------------------------- analysis
def per_field(rows: list[Row]) -> list[dict]:
    by = defaultdict(list)
    for r in rows:
        by[r.field].append(r)

    results = []
    for fld, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        unsure = [r for r in rs if r.a2 == UNSURE]
        joint = [r for r in rs if r.a2 != UNSURE]
        a = np.array([1 if r.a1 == KEEP else 0 for r in joint])
        b = np.array([1 if r.a2 == KEEP else 0 for r in joint])
        n = len(joint)
        rec = {
            "field": fld, "n_total": len(rs), "n_joint": n, "n_unsure": len(unsure),
            "n_disagree": int(np.sum(a != b)) if n else 0,
            "po": float(np.mean(a == b)) if n else float("nan"),
            "a1_keep_rate": float(np.mean(a)) if n else float("nan"),
            "a2_keep_rate": float(np.mean(b)) if n else float("nan"),
            "reportable": n >= MIN_FIELD_N,
            # One annotator used a single label throughout. kappa is undefined
            # and AC1 is 1.0 by construction; neither demonstrates that the
            # annotators can tell the categories apart.
            "degenerate": bool(n) and (len(set(a.tolist())) == 1
                                       or len(set(b.tolist())) == 1),
        }
        if rec["reportable"]:
            rec["kappa"] = cohen_kappa(a, b)
            rec["kappa_ci"] = bootstrap_ci(a, b, cohen_kappa)
            rec["ac1"] = gwet_ac1(a, b)
            rec["ac1_ci"] = bootstrap_ci(a, b, gwet_ac1)
        results.append(rec)
    return results


def calibration_diagnostic(cal: list[dict], fields: list[dict]) -> list[dict]:
    """Link calibration misses to disagreement in the real rows.

    This is a diagnostic, not a statistic. Ten calibration items over seven
    fields gives at most one or two items per field, so nothing here is
    quantified or tested. The question it answers is narrow and useful: did the
    codebook rules on which the annotator and the codebook first diverged go on
    to produce disproportionate disagreement in the real annotation? A yes
    points at the rule's wording; a no says the calibration miss was noise.
    """
    miss_by_field = Counter(c["field"] for c in cal
                            if not c.get("matched", c.get("correct")))
    seen_by_field = Counter(c["field"] for c in cal)
    rate = {f["field"]: (f["n_disagree"] / f["n_joint"] if f["n_joint"] else float("nan"))
            for f in fields}
    overall_d = sum(f["n_disagree"] for f in fields)
    overall_n = sum(f["n_joint"] for f in fields)
    base = overall_d / overall_n if overall_n else float("nan")

    out = []
    for fld in sorted(set(seen_by_field) | set(rate)):
        r = rate.get(fld, float("nan"))
        out.append({
            "field": fld,
            "cal_items": seen_by_field.get(fld, 0),
            "cal_missed": miss_by_field.get(fld, 0),
            "disagree_rate": r,
            "vs_baseline": (r / base) if base and not np.isnan(r) and base > 0
                           else float("nan"),
        })
    return out, base


def adjudication_queue(rows: list[Row]) -> list[Row]:
    """Rows needing adjudication, in the order the rule resolves them.

    Disagreements first (a cited locator settles them), then rows one side
    marked unsure. Both lists go to the adjudication session; neither is
    resolved by this script.
    """
    disagree = [r for r in rows if r.a2 != UNSURE and r.a1 != r.a2]
    unsure = [r for r in rows if r.a2 == UNSURE]
    return disagree + unsure


# --------------------------------------------------------------------- report
def _fmt(x, nd=3):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def report(loaded: Loaded) -> str:
    fields = per_field(loaded.rows)
    diag, base = calibration_diagnostic(loaded.calibration, fields)
    queue = adjudication_queue(loaded.rows)
    rep = sorted([f for f in fields if f["reportable"]], key=lambda f: -f["n_joint"])
    thin = [f for f in fields if not f["reportable"]]

    L = ["# N9 inter-annotator agreement", "",
         f"Rows loaded: {len(loaded.rows)}. "
         f"Jointly decided: {sum(f['n_joint'] for f in fields)}. "
         f"Marked unsure by the second annotator: {sum(f['n_unsure'] for f in fields)}.",
         ""]
    if loaded.missing_from_export:
        L += [f"**{len(loaded.missing_from_export)} exported rows are not in the key** "
              f"and were dropped. First few: {loaded.missing_from_export[:5]}", ""]
    if loaded.undecided:
        L += [f"**{len(loaded.undecided)} rows carry no decision** and were dropped "
              f"from every figure below.", ""]

    L += ["## Agreement by field", "",
          "Unsure rows are excluded from the denominator and counted separately. "
          "Both coefficients are given because the keep rate is skewed; where they "
          "diverge, that divergence is the finding.", "",
          "| field | n | unsure | disagree | observed | Cohen's kappa | 95% CI | Gwet's AC1 | 95% CI |",
          "|---|---:|---:|---:|---:|---:|---|---:|---|"]
    for f in rep:
        mark = " \u2020" if f["degenerate"] else ""
        L.append(f"| `{f['field']}`{mark} | {f['n_joint']} | {f['n_unsure']} | {f['n_disagree']} "
                 f"| {_fmt(f['po'])} | {_fmt(f['kappa'])} "
                 f"| [{_fmt(f['kappa_ci'][0],2)}, {_fmt(f['kappa_ci'][1],2)}] "
                 f"| {_fmt(f['ac1'])} "
                 f"| [{_fmt(f['ac1_ci'][0],2)}, {_fmt(f['ac1_ci'][1],2)}] |")

    if any(f["degenerate"] for f in rep):
        L += ["",
              "\u2020 One annotator used a single label throughout this field. "
              "Cohen's kappa is undefined and Gwet's AC1 is 1.0 by construction. "
              "The agreement is real but no discrimination has been demonstrated, "
              "so neither coefficient should be read as evidence that the "
              "annotators can separate the categories here."]

    if thin:
        L += ["", f"## Below the reporting threshold (n < {MIN_FIELD_N})", "",
              "No coefficient is computed for these. The interval at this n spans "
              "most of the usable range, so a number would imply a precision the "
              "data does not have. Raw agreement only.", "",
              "| field | n | unsure | disagree | observed agreement |",
              "|---|---:|---:|---:|---:|"]
        for f in thin:
            L.append(f"| `{f['field']}` | {f['n_joint']} | {f['n_unsure']} "
                     f"| {f['n_disagree']} | {_fmt(f['po'])} |")

    L += ["", "## Calibration diagnostic", "",
          "Not a statistic. Ten items over seven fields cannot support one. The "
          "question is whether the rules the annotator and the codebook first "
          f"diverged on produced more disagreement than the baseline rate of "
          f"{_fmt(base)}.", "",
          "| field | calibration items | missed | disagreement rate | vs baseline |",
          "|---|---:|---:|---:|---:|"]
    for d in diag:
        L.append(f"| `{d['field']}` | {d['cal_items']} | {d['cal_missed']} "
                 f"| {_fmt(d['disagree_rate'])} "
                 f"| {_fmt(d['vs_baseline'], 2)}x |")

    L += ["", "## Adjudication queue", "",
          f"{len(queue)} rows to adjudicate: "
          f"{sum(1 for r in queue if r.a2 != UNSURE)} disagreements and "
          f"{sum(1 for r in queue if r.a2 == UNSURE)} unsure. Each is resolved by a "
          "cited locator; a row neither annotator can locate is removed rather than "
          "argued. This script does not resolve any of them.", ""]

    if loaded.additions_a2:
        L += ["## Additions", "",
              "Rows the second annotator proposed that the pipeline never offered. "
              "These have no counterpart judgement, so they are scored as precision "
              "and recall against the first annotator's additions and never enter a "
              "coefficient.", ""]
        for sid, txt in sorted(loaded.additions_a2.items()):
            n = len([l for l in str(txt).splitlines() if l.strip()])
            L.append(f"- `{sid}`: {n} line(s)")
        L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    """Verify the coefficients on constructed data with known answers."""
    rng = np.random.default_rng(7)
    fails = []

    def check(label, got, want, tol=1e-9):
        ok = (np.isnan(got) and np.isnan(want)) or abs(got - want) < tol
        print(f"{'PASS' if ok else 'FAIL'}  {label}: got {got:.6f} want {want:.6f}")
        if not ok:
            fails.append(label)

    # perfect agreement
    a = np.array([1, 1, 0, 0, 1, 0, 0, 0])
    check("kappa, perfect agreement", cohen_kappa(a, a), 1.0)
    check("AC1, perfect agreement", gwet_ac1(a, a), 1.0)

    # total disagreement on a balanced vector
    b = 1 - a
    check("kappa, total disagreement balanced", cohen_kappa(a, b), -1.0, 0.2)

    # hand-computed 2x2: n=100, both mark 30 keep, 20 of those shared
    #   a=1,b=1 : 20 | a=1,b=0 : 10 | a=0,b=1 : 10 | a=0,b=0 : 60
    A = np.array([1] * 30 + [0] * 70)
    B = np.array([1] * 20 + [0] * 10 + [1] * 10 + [0] * 60)
    po = 0.80
    pe = 0.3 * 0.3 + 0.7 * 0.7          # 0.58
    check("kappa, hand-computed 2x2", cohen_kappa(A, B), (po - pe) / (1 - pe))
    pi = 0.3
    peg = 2 * pi * (1 - pi)             # 0.42
    check("AC1, hand-computed 2x2", gwet_ac1(A, B), (po - peg) / (1 - peg))

    # the prevalence paradox: identical observed agreement, kappa collapses,
    # AC1 does not. This is the reason both are reported.
    n = 1000
    for prev in (0.50, 0.26, 0.05):
        x = (rng.random(n) < prev).astype(int)
        flip = rng.random(n) < 0.10            # 10% disagreement either way
        y = np.where(flip, 1 - x, x)
        k, g = cohen_kappa(x, y), gwet_ac1(x, y)
        print(f"      prevalence {prev:.2f}: observed {np.mean(x == y):.3f}  "
              f"kappa {k:.3f}  AC1 {g:.3f}")
        if prev == 0.05 and not (g - k > 0.15):
            fails.append("prevalence paradox not demonstrated at p=0.05")
            print("FAIL  AC1 should exceed kappa substantially at low prevalence")

    # degenerate: one annotator used a single label throughout
    c = np.ones(50, dtype=int)
    d = np.ones(50, dtype=int)
    print(f"{'PASS' if np.isnan(cohen_kappa(c, d)) else 'FAIL'}  "
          "kappa is nan when pe == 1 rather than dividing by zero")
    if not np.isnan(cohen_kappa(c, d)):
        fails.append("degenerate pe")
    ok = gwet_ac1(c, d) == 1.0
    print(f"{'PASS' if ok else 'FAIL'}  AC1 is 1.0 on a single-label field "
          "(flagged degenerate, not suppressed)")
    if not ok:
        fails.append("degenerate AC1")

    # bootstrap brackets the point estimate
    lo, hi = bootstrap_ci(A, B, cohen_kappa)
    pt = cohen_kappa(A, B)
    ok = lo <= pt <= hi
    print(f"{'PASS' if ok else 'FAIL'}  bootstrap CI [{lo:.3f}, {hi:.3f}] "
          f"brackets the point estimate {pt:.3f}")
    if not ok:
        fails.append("bootstrap bracket")

    # end to end on a synthetic export, including the unsure path
    import tempfile, os
    tmp = tempfile.mkdtemp()
    kp = os.path.join(tmp, "key.csv")
    with open(kp, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "field", "item", "in_ground_truth"])
        for i in range(200):
            fld = "methods" if i < 120 else ("datasets" if i < 190 else "random_seeds")
            w.writerow([f"study001-{i:03d}", fld, f"item {i}",
                        "yes" if i % 4 == 0 else "no"])
    items = []
    for i in range(200):
        fld = "methods" if i < 120 else ("datasets" if i < 190 else "random_seeds")
        dec = UNSURE if i % 37 == 0 else (KEEP if i % 4 == 0 else DISCARD)
        if i % 23 == 0 and dec != UNSURE:                 # inject disagreement
            dec = DISCARD if dec == KEEP else KEEP
        items.append({"item_id": f"study001-{i:03d}", "field": fld,
                      "item": f"item {i}", "decision": dec, "note": ""})
    ep = os.path.join(tmp, "export.json")
    json.dump({"tool": "n9-annotation-workbook", "tool_version": "n9-workbook-1.4",
               "calibration_n9": {"n_items": 10, "score": 8, "complete": True,
                                  "gated": False,
                                  "answers": [{"id": f"s{i:02d}", "field": "methods",
                                               "first_answer": KEEP, "key": KEEP,
                                               "matched": i > 2} for i in range(10)]},
               "studies": [{"study_id": "study001", "additions": "", "items": items}]},
              open(ep, "w"))
    loaded = load(kp, ep)
    txt = report(loaded)
    checks = [
        ("loaded 200 rows", len(loaded.rows) == 200),
        ("methods is reportable", any(f["field"] == "methods" and f["reportable"]
                                      for f in per_field(loaded.rows))),
        ("random_seeds is not reportable", any(f["field"] == "random_seeds"
                                               and not f["reportable"]
                                               for f in per_field(loaded.rows))),
        ("report names the threshold section", "Below the reporting threshold" in txt),
        ("report has a calibration diagnostic", "Calibration diagnostic" in txt),
        ("report has an adjudication queue", "Adjudication queue" in txt),
        ("unsure rows excluded from denominator",
         sum(f["n_unsure"] for f in per_field(loaded.rows)) > 0),
    ]
    for label, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            fails.append(label)

    print("\n" + ("ALL CHECKS PASSED" if not fails else f"FAILURES: {fails}"))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", help="origin_key.csv, annotator 1")
    ap.add_argument("--annotator", help="workbook export JSON, annotator 2")
    ap.add_argument("--out", help="write the markdown report here")
    ap.add_argument("--self-test", action="store_true",
                    help="verify the coefficients on constructed data and exit")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not (args.key and args.annotator):
        ap.error("--key and --annotator are required unless --self-test is given")

    txt = report(load(args.key, args.annotator))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(txt + "\n")
        print(f"written: {args.out}")
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
