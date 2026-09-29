"""Tier-B results: variance, attribution, and discrimination.

Three questions, in order of importance to the paper:

Q1  Do the Tier-B criteria vary across the corpus? FAIR-R forfeits 57.8 of 100
    points identically for all 96 repositories; a replacement that saturates the
    same way would be no improvement.

Q2  **Attribution.** For each failure the workshop paper attributes to a missing
    or placeholder command, did the repository actually document a usable one?
    The recipe label records what the *extractor produced*; Tier B records what
    the *artifact documents*. Where they disagree, the failure belongs to the
    extractor, not the author — which moves it from `author-fix` to
    `extraction-research` on the taxonomy's remedy axis.

Q3  Do Tier-B criteria predict Level-1 outcomes better than FAIR-R, the licence
    bit, or the Tier-A deterministic set?

Usage:  python3 analysis/tier_b_analysis.py
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parent.parent
TIER_B = ROOT / "validation" / "tier_b"
RESULTS = ROOT / "validation" / "results"
ROWS = ROOT / "result_repro" / "results" / "rows"
OUT_MD = ROOT / "analysis" / "tier_b_analysis.md"
OUT_CSV = ROOT / "analysis" / "tier_b_crosstab.csv"
SID = re.compile(r"^study\d{3}$")
LEVEL = {"absent": 0, "partial": 1, "full": 2}

CHECKS = ["concrete_run_command", "documented_entrypoint", "links_resolve",
          "data_obtainable_without_application", "repo_matches_paper"]


def load_tier_b() -> dict[str, dict]:
    out = {}
    for p in sorted(glob.glob(str(TIER_B / "study*.json"))):
        d = json.load(open(p))
        if d.get("status") == "ok":
            out[d["study_id"]] = d
    return out


def load_outcomes() -> dict[str, dict]:
    out = {}
    for p in sorted(glob.glob(str(RESULTS / "study*.json"))):
        d = json.load(open(p))
        if SID.match(str(d.get("study_id", ""))):
            out[d["study_id"]] = d
    return out


def load_rows() -> dict[str, dict]:
    out = {}
    for p in sorted(glob.glob(str(ROWS / "study*.json"))):
        d = json.load(open(p))
        if SID.match(str(d.get("study_id", ""))):
            out[d["study_id"]] = d
    return out


def mode_of(reason: str) -> str:
    r = (reason or "").lower()
    if "placeholder" in r:                              return "placeholder recipe"
    if "no run command" in r:                           return "no run command"
    if "mismatch" in r:                                 return "repo != paper"
    if "dead_download" in r or "gated_download" in r:   return "dead download"
    if "missing_file_or_data" in r:                     return "gated dataset"
    if "no numeric claim" in r:                         return "(excl) no claim"
    if "out-of-scale" in r:                             return "(excl) out of scale"
    if "hardware-bound" in r:                           return "(excl) hardware metric"
    if "a/b" in r or "production" in r:                 return "(excl) online metric"
    if "mobile device" in r or "emulator" in r:         return "(excl) external device"
    if "missing_dependency" in r or "missing_system_dep" in r: return "(harness) missing dep"
    return "?"


def cv(X, y, reps=20):
    s = []
    for r in range(reps):
        for tr, te in StratifiedKFold(10, shuffle=True, random_state=r).split(X, y):
            m = LogisticRegression(max_iter=2000).fit(X[tr], y[tr])
            s.append(roc_auc_score(y[te], m.predict_proba(X[te])[:, 1]))
    return float(np.mean(s)), float(np.std(s))


def main() -> int:
    tb, outc, rows = load_tier_b(), load_outcomes(), load_rows()
    L, A = [], None
    L = []; A = L.append

    A(f"# Tier-B results (n={len(tb)} repositories checked)\n")
    A("Regenerate with `python3 analysis/tier_b_analysis.py`. "
      "Checks defined in `build_harness/tier_b_checks.py`; swept by "
      "`build_harness/tier_b_corpus.sbatch`.\n")

    # ---------------------------------------------------------------- Q1
    A("## Q1 — Do the Tier-B criteria vary?\n")
    A("| Criterion | absent | partial | full | sd (0/1/2) | varies usefully |")
    A("|---|---:|---:|---:|---:|:--:|")
    dist = {}
    for c in CHECKS:
        vals = [LEVEL[tb[s]["checks"][c]["level_name"]] for s in tb]
        cnt = Counter(tb[s]["checks"][c]["level_name"] for s in tb)
        dist[c] = np.array(vals, dtype=float)
        minority = len(vals) - max(cnt.values())
        A(f"| {c} | {cnt['absent']} | {cnt['partial']} | {cnt['full']} | "
          f"{np.std(vals):.2f} | {'yes' if minority >= 5 else '**near-constant**'} |")
    A("")
    A("- **Four of five vary substantially.** Compare FAIR-R, where 9 of 15 "
      "criteria are identical for all 96 repositories and only 3 are usable.")
    A("- `data_obtainable_without_application` is the exception (94 full / 2 "
      "absent). It has the same saturation problem this paper criticises FAIR-R "
      "for, and should be reported as such rather than quietly kept: gated data "
      "is real but rare, so it cannot carry discrimination even though it caused "
      "a genuine failure.")
    A("")
    cr = Counter(tb[s]["checks"]["concrete_run_command"]["level_name"] for s in tb)
    A(f"**Standalone corpus finding:** only **{cr['full']} of {len(tb)} "
      f"({100*cr['full']/len(tb):.0f}%)** repositories document a concrete command "
      f"that reproduces a reported metric. {cr['partial']} document commands but "
      f"none that reproduces a metric (or only placeholder ones), and "
      f"{cr['absent']} document no runnable command at all. This is measured "
      "deterministically from the documentation, with no language model involved.")

    # ---------------------------------------------------------------- Q2
    A("\n## Q2 — Attribution: the author's gap, or the extractor's?\n")
    buildable = {s: rows[s] for s in rows}
    recs = []
    for s, r in sorted(buildable.items()):
        if s not in tb:
            continue
        c = tb[s]["checks"]["concrete_run_command"]
        d = c["detail"]
        recs.append(dict(
            study_id=s, mode=mode_of(r.get("reason", "")),
            recipe_status=r.get("status", ""),
            docs_grade=c["level_name"],
            n_eval_concrete=d.get("n_eval_concrete", 0),
            n_eval_placeholder=d.get("n_eval_placeholder", 0),
            evidence=c["evidence"][:120]))
    df = pd.DataFrame(recs)

    cmd_modes = ["placeholder recipe", "no run command"]
    sub = df[df["mode"].isin(cmd_modes)]
    A(f"The workshop paper attributes **{len(sub)} of the 16 artifact failures** "
      "to a command problem (7 placeholder + 4 no-command, plus any reclassified). "
      "Tier B asks, independently and deterministically, whether the repository "
      "documented a usable command anyway.\n")
    A("| Failure mode | docs: full | docs: partial | docs: absent |")
    A("|---|---:|---:|---:|")
    for m in cmd_modes:
        row = df[df["mode"] == m]
        g = Counter(row["docs_grade"])
        A(f"| {m} (n={len(row)}) | {g['full']} | {g['partial']} | {g['absent']} |")
    mis = sub[sub["docs_grade"] == "full"]
    A("")
    A(f"**{len(mis)} of {len(sub)} command-related failures occurred in "
      f"repositories that DO document a concrete evaluation command.** In those "
      "cases the artifact is not at fault: the extractor selected a placeholder "
      "command, or missed the documented one. On the taxonomy's remedy axis these "
      "move from `author-fix` to `extraction-research`.\n")
    if len(mis):
        A("| Study | Mode | concrete eval cmds in docs | placeholder eval cmds | evidence |")
        A("|---|---|---:|---:|---|")
        for _i, r in mis.iterrows():
            A(f"| {r.study_id} | {r['mode']} | {r.n_eval_concrete} | "
              f"{r.n_eval_placeholder} | `{r.evidence[:70]}` |")
    A("")
    A("This makes quantitative what the workshop paper could previously only infer "
      "from a 3-artifact ablation (autonomous 0/3, gold recipes 2/3): extraction, "
      "not artifact quality, is the binding constraint for a measurable share of "
      "the corpus.")

    A("\n### Full cross-tabulation (26 buildable)\n")
    A("| Study | Failure mode | Recipe status | Docs grade |")
    A("|---|---|---|---|")
    for _i, r in df.sort_values(["mode", "study_id"]).iterrows():
        A(f"| {r.study_id} | {r['mode']} | `{r.recipe_status}` | `{r.docs_grade}` |")

    # ---------------------------------------------------------------- Q3
    A("\n## Q3 — Do Tier-B criteria predict Level-1 outcomes?\n")
    ids = [s for s in tb if s in outc and
           (outc[s].get("build") or {}).get("resolve_success") is not None]
    yb = {o: np.array([int(bool((outc[s].get("build") or {})[o])) for s in ids])
          for o in ("resolve_success", "build_success")}
    Xb = np.array([[LEVEL[tb[s]["checks"][c]["level_name"]] for c in CHECKS] for s in ids],
                  dtype=float)
    v1 = np.array([[outc[s]["fair_r"]["total_score"]] for s in ids], dtype=float)
    lic = np.array([[int(bool((outc[s].get("repo_meta") or {}).get("software_license")))]
                    for s in ids], dtype=float)
    Xall = np.hstack([Xb, lic])
    A(f"n={len(ids)} build-attempted. 10-fold CV, 20 repeats.\n")
    A("| Outcome | Instrument | CV AUC |")
    A("|---|---|---:|")
    for o in ("resolve_success", "build_success"):
        for lab, X in (("FAIR-R v1 (aggregate)", v1),
                       ("Software licence alone", lic),
                       ("Tier-B (5 checks)", Xb),
                       ("Tier-B + licence", Xall)):
            m, s = cv(X, yb[o])
            A(f"| `{o}` | {lab} | {m:.3f} ± {s:.3f} |")
    A("")
    A("Tier-B criteria were designed to explain *result-level* reproduction "
      "failure, not environment reconstruction, so Level-1 is the wrong outcome "
      "for them and a modest result here is expected rather than disappointing. "
      "No Level-2 outcome exists to test against — nothing in the corpus "
      "reproduced — which is itself the limitation to state plainly.")

    df.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[tier-b] wrote {OUT_MD} and {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
