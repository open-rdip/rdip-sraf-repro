"""Restructure the reproduction-failure taxonomy for the journal extension.

The workshop paper reports one taxonomy in three families over 26 buildable
repositories: documentation/artifact gaps (18), not-reproducible-by-construction
(4), and our-environment (4). The three are not the same kind of thing:

  * documentation/artifact gaps are findings about the research artifact;
  * not-reproducible-by-construction cases are EXCLUSIONS — the paper itself
    says they are "excluded by design rather than counted against the artifact";
  * our-environment cases are MEASUREMENT ERROR in our harness, which the paper
    already isolates as a threat to validity.

Reporting "18 of 26" therefore divides genuine artifact failures by a
denominator that also contains exclusions and our own bugs, which understates
the result. This script separates them and re-expresses the taxonomy on two
axes:

  Axis 1 - LOCUS  : whose problem is it (artifact / claim / scope / harness)
  Axis 2 - REMEDY : who can fix it (author-fix / extraction-research /
                    harness-fix / intrinsic), the three-way split the workshop
                    paper's discussion already makes without naming it as an axis

It also maps each artifact-side failure mode onto the FAIR-R criterion that
would have caught it, which is the bridge to the instrument redesign.

Two assignments are judgement calls and are flagged as such; they are exactly
what the inter-rater study should adjudicate. Usage:

    python3 analysis/taxonomy_restructure.py
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROWS = REPO_ROOT / "result_repro" / "results" / "rows"
OUT_MD = REPO_ROOT / "analysis" / "taxonomy_restructured.md"
OUT_CODING = REPO_ROOT / "analysis" / "taxonomy_coding_sheet.csv"

# ---------------------------------------------------------------- the scheme
# locus:  artifact | claim | scope | harness
# remedy: author-fix | extraction-research | harness-fix | intrinsic
MODES = {
    "placeholder_recipe": dict(
        mode="Placeholder command", locus="artifact",
        remedy="author-fix", also="extraction-research",
        fairr="NOT COVERED - no criterion asks whether the run command is concrete",
    ),
    "no_run_command": dict(
        mode="No run command", locus="artifact",
        remedy="author-fix", also="extraction-research",
        fairr="Reproducible R2 (methodological transparency) - partial coverage only",
    ),
    "repo_paper_mismatch": dict(
        mode="Repository does not match paper", locus="artifact",
        remedy="author-fix", also=None,
        fairr="Interoperable / Related links - INVARIANT (absent for all 96)",
    ),
    "dead_download": dict(
        mode="Dead download (link rot)", locus="artifact",
        remedy="author-fix", also=None,
        fairr="NOT COVERED - no criterion tests link liveness",
    ),
    "gated_data": dict(
        mode="Gated dataset", locus="artifact",
        remedy="author-fix", also=None,
        fairr="Accessible / Access level - INVARIANT (absent for all 96)",
    ),
    "no_numeric_claim": dict(
        mode="No numeric claim to test", locus="claim",
        remedy="intrinsic", also=None,
        fairr="Reproducible R2 - reporting gap, but nothing to reproduce against",
        judgement="Workshop paper filed this under documentation/artifact gaps. "
                  "Moved: with no claimed number there is no reproduction to test, "
                  "so it is an exclusion, not a failure.",
    ),
    "out_of_scale": dict(
        mode="Out of scale for the harness", locus="scope",
        remedy="intrinsic", also=None,
        fairr="n/a - a property of our 1x48GB envelope, not of the artifact",
        judgement="Workshop paper filed this under documentation/artifact gaps. "
                  "Moved: a 176B model is outside the harness's declared operating "
                  "envelope, which is the definition of an exclusion.",
    ),
    "hardware_bound": dict(
        mode="Hardware-bound metric", locus="claim",
        remedy="intrinsic", also=None, fairr="n/a - metric not reproducible by construction"),
    "online_metric": dict(
        mode="Production/online metric", locus="claim",
        remedy="intrinsic", also=None, fairr="n/a - metric not reproducible by construction"),
    "external_device": dict(
        mode="Needs external device or service", locus="claim",
        remedy="intrinsic", also=None, fairr="n/a - metric not reproducible by construction"),
    "harness_missing_dep": dict(
        mode="Dependency absent from our harness", locus="harness",
        remedy="harness-fix", also=None, fairr="n/a - measurement error, not a finding"),
}

LOCUS_LABEL = {
    "artifact": "Artifact failure (a finding)",
    "claim":    "Excluded - claim not reproducible by construction",
    "scope":    "Excluded - outside harness scope",
    "harness":  "Measurement error - our harness",
}


def classify(reason: str) -> str:
    """Map a recorded reason string onto a mode key."""
    r = (reason or "").lower()
    if "placeholder" in r:                              return "placeholder_recipe"
    if "no run command" in r:                           return "no_run_command"
    if "mismatch" in r:                                 return "repo_paper_mismatch"
    if "dead_download" in r or "gated_download" in r:   return "dead_download"
    if "missing_file_or_data" in r:                     return "gated_data"
    if "no numeric claim" in r or "no claimed number" in r: return "no_numeric_claim"
    if "out-of-scale" in r or "out_of_scale" in r:      return "out_of_scale"
    if "hardware-bound" in r:                           return "hardware_bound"
    if "a/b" in r or "production" in r:                 return "online_metric"
    if "mobile device" in r or "emulator" in r or "external" in r: return "external_device"
    if "missing_dependency" in r or "missing_system_dep" in r:     return "harness_missing_dep"
    return "UNCLASSIFIED"


def main() -> int:
    rows = [json.load(open(p)) for p in sorted(glob.glob(str(ROWS / "*.json")))]
    corpus = [r for r in rows if str(r.get("study_id", "")).startswith("study")]
    L, A = [], None
    L = []
    A = L.append

    A(f"# Restructured failure taxonomy (n={len(corpus)} buildable repositories)\n")
    A("Regenerate with `python3 analysis/taxonomy_restructure.py`. "
      "The workshop paper's three families are separated here into findings, "
      "exclusions and measurement error, then re-expressed on two axes.\n")

    recs = []
    for r in sorted(corpus, key=lambda x: x["study_id"]):
        key = classify(r.get("reason", ""))
        spec = MODES.get(key, dict(mode="UNCLASSIFIED", locus="?", remedy="?", fairr="?"))
        recs.append(dict(study_id=r["study_id"], reason=r.get("reason", ""), key=key, **spec))

    unclassified = [x for x in recs if x["key"] == "UNCLASSIFIED"]
    if unclassified:
        A("> **Unclassified rows present — fix `classify()` before using this.**\n")
        for u in unclassified:
            A(f"> - {u['study_id']}: `{u['reason']}`")
        A("")

    # ------------------------------------------------------------ the split
    by_locus = defaultdict(list)
    for x in recs:
        by_locus[x["locus"]].append(x)

    A("## 1. The three families are not the same kind of thing\n")
    A("| Locus | n | What it is |")
    A("|---|---:|---|")
    for loc in ("artifact", "claim", "scope", "harness"):
        A(f"| `{loc}` | {len(by_locus[loc])} | {LOCUS_LABEL[loc]} |")
    A("")
    n_art = len(by_locus["artifact"])
    n_excl = len(by_locus["claim"]) + len(by_locus["scope"])
    n_harn = len(by_locus["harness"])
    A(f"- **Genuine artifact failures: {n_art}.** Exclusions: {n_excl}. "
      f"Measurement error: {n_harn}.")
    A(f"- The workshop paper reports **18 of 26** as documentation/artifact gaps. "
      f"Once exclusions and our own harness bugs leave the denominator, the claim "
      f"becomes **{n_art} of {n_art}** — every genuine artifact failure in the corpus "
      f"is a documentation or artifact gap. Not compute, not fundamental difficulty.")
    A(f"- Two studies move out of the paper's family 1 on judgement (see §4); that is "
      f"why this is {n_art}, not 18.")

    # ------------------------------------------------------------ two axes
    A("\n## 2. Two-axis taxonomy\n")
    A("Axis 1 is *whose problem it is*; axis 2 is *who can fix it* — the three-way "
      "remedy split the workshop discussion already makes. Crossing them turns a flat "
      "list into guidance about where effort should go.\n")
    A("| Failure mode | n | Locus | Primary remedy | Also addressable by |")
    A("|---|---:|---|---|---|")
    cnt = Counter(x["key"] for x in recs)
    seen = set()
    for x in sorted(recs, key=lambda y: (y["locus"], -cnt[y["key"]], y["mode"])):
        if x["key"] in seen:
            continue
        seen.add(x["key"])
        A(f"| {x['mode']} | {cnt[x['key']]} | `{x['locus']}` | `{x['remedy']}` | "
          f"{'`'+x['also']+'`' if x.get('also') else '—'} |")

    A("")
    A("| | author-fix | extraction-research | harness-fix | intrinsic |")
    A("|---|---:|---:|---:|---:|")
    for loc in ("artifact", "claim", "scope", "harness"):
        c = Counter(x["remedy"] for x in by_locus[loc])
        A(f"| `{loc}` | {c['author-fix']} | {c['extraction-research']} | "
          f"{c['harness-fix']} | {c['intrinsic']} |")

    # ------------------------------------------- bridge to the instrument
    A("\n## 3. Which FAIR-R criterion would have caught each artifact failure?\n")
    A("This is the bridge from the taxonomy to the instrument redesign: if the rubric "
      "already scored the thing that broke, a good score should have predicted success. "
      "It mostly doesn't — the modes map onto criteria that are either absent from the "
      "rubric entirely or among the ones that never vary.\n")
    A("| Failure mode | n | Covered by FAIR-R? |")
    A("|---|---:|---|")
    seen = set()
    for x in sorted(by_locus["artifact"], key=lambda y: -cnt[y["key"]]):
        if x["key"] in seen:
            continue
        seen.add(x["key"])
        A(f"| {x['mode']} | {cnt[x['key']]} | {x['fairr']} |")
    A("")
    A("**Read this with the variance audit.** The criteria these failures map onto are "
      "either *not in the rubric at all* (concrete run command, link liveness) or are "
      "among the 57.8 points that are invariant across all 96 repositories (Related "
      "links, Access level). So the instrument could not have predicted these failures "
      "even in principle. That is the mechanism behind the null result, and it is the "
      "argument for a code-native criterion set rather than a re-weighting.")

    # ------------------------------------------------------- judgement calls
    A("\n## 4. Judgement calls for the inter-rater study\n")
    A("These two reassignments change the headline denominator and should be "
      "adjudicated by the second coder rather than asserted:\n")
    for x in recs:
        if x.get("judgement"):
            A(f"- **{x['study_id']} — {x['mode']}.** {x['judgement']}")
    A("\nEverything else follows mechanically from the recorded reason string.")

    # ------------------------------------------------------- per-study table
    A("\n## 5. Per-study assignment\n")
    A("| Study | Recorded reason | Mode | Locus | Remedy |")
    A("|---|---|---|---|---|")
    for x in recs:
        A(f"| {x['study_id']} | `{x['reason'][:58]}` | {x['mode']} | "
          f"`{x['locus']}` | `{x['remedy']}` |")

    OUT_MD.write_text("\n".join(L) + "\n")

    # coding sheet: artifact-side cases only, blanked for the second coder
    import csv
    with open(OUT_CODING, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["study_id", "repo_url", "recorded_reason",
                    "coder2_locus", "coder2_remedy", "coder2_notes"])
        by_id = {r["study_id"]: r for r in corpus}
        for x in recs:
            w.writerow([x["study_id"], by_id[x["study_id"]].get("repo_url", ""),
                        x["reason"], "", "", ""])

    print("\n".join(L))
    print(f"\n[taxonomy] wrote {OUT_MD}")
    print(f"[taxonomy] wrote {OUT_CODING} — blank coding sheet for the second rater")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
