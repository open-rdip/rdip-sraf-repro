# Journal Extension — New Generation Computing (Springer)

**Status:** v2, 10 Sept 2026. Supersedes v1 (archived as
`journal_extension_plan_v1_archived.md`, written before the workshop paper existed —
its WS1 *became* that paper).

**Venue.** New Generation Computing (Springer; official journal of JSAI since 2023;
IF 2.1; median 107 days to first decision). IJCKG 2026 states that selected papers
are invited to a NGC special issue "subject to the journal's review process". The
collection is **not yet open** on Springer — timeline unknown, must be confirmed
with the organisers.

---

## 1. Novelty accounting — what now counts as prior work

Both source papers are (or will be) published, so neither counts toward the
40–50% new-contribution requirement:

| Source | Venue | Status | Contributes as |
|---|---|---|---|
| RDIP ontology | TPDL 2026 | accepted | cited background |
| SRAF (measurement) | IJCKG 2026 main | accepted, camera-ready done | **prior work** |
| Result-level reproduction | IJCKG 2026 workshop (CEUR) | submitting 10 Sep | **prior work** (if published) |

**Consequence.** `rdip:ExecutionRecipe`, the two-phase engine, the failure taxonomy
and the positive-control ablation move from "new material" to "prior work". That
removes ~35–40 points of novelty budget. The components in §3 replace it.

**Open question — ask the SI editors before writing.** Whether one journal
submission may extend *both* the main-track and the workshop paper. If only the
invited main-track paper may be extended, the workshop content returns to the new
column and the budget becomes trivially satisfied — but the answer changes the
structure, so get it early. Workshop camera-ready is 30 Sep; notification 25 Sep.

**Structural rule.** Do **not** write "SRAF chapter + workshop chapter + new
chapter". Write a paper whose *thesis* is new (§2) and compress both prior papers
into the methods and setup that thesis requires. A reviewer who can see the seams
will score it as an incremental merge.

---

## 2. The new thesis

> Reproducibility scores measure how well a study is *described*, not whether it
> *reproduces*. We show this at two levels on 96 ML repositories, explain the
> failure mechanically — most of a FAIR-style rubric is invariant on executable
> artifacts — identify the small set of deterministic features that do carry
> signal, and turn that into a triage procedure for spending verification effort.

This is a claim about the FAIR-assessment literature, not only about SRAF. Neither
source paper makes it; both become evidence for it.

---

## 3. Contribution budget

Target ~28–30 pages (Springer). Carried material is **compressed**, not reproduced.

### Carried over — ~12 pp (≈ 43%)

| id | Content | Source | Pages |
|---|---|---|---:|
| C1 | RDIP profile + FAIR-R rubric | SRAF §3 | 3.0 |
| C2 | Corpus (96 repos) + reconstruction protocol | SRAF §4.3 | 1.5 |
| C3 | Level-1 results: 55.8% resolve / 52.3% build | SRAF §4.4–4.6 | 2.5 |
| C4 | `rdip:ExecutionRecipe` + two-phase engine | Workshop §3 | 2.5 |
| C5 | Failure taxonomy + positive controls (2/3) | Workshop §4–5 | 2.5 |

### New — ~19 pp (≈ 57%, trims to 45–50% after editing)

| id | Contribution | Pages | Effort | Cost | Status |
|---|---|---:|---|---|---|
| **N1** | **Criterion-level predictive validity + variance audit.** 57.8/100 points invariant across all 96 repos; only 3 criteria usable. Firth penalized regression (EPV 15–16), BH-FDR + Bonferroni, cross-validated AUC, FAIR-R v1 vs v2 vs licence-only. | 4.0 | — | — | **DONE** (`analysis/criterion_validity.py`) |
| **N2** | **Generality across instruments.** Run the same variance audit on F-UJI / FAIRshake / the ML Reproducibility Checklist over the same 96 repos. If they saturate too, the claim generalises beyond SRAF — this is what makes it a literature-level contribution rather than a self-critique. | 3.0 | medium | free | not started |
| **N3** | **Frontier-model extraction + robustness re-run (WS3).** Extend Table 5 with 2–3 API models; then **re-score the corpus with the best extractor and re-run N1**. Answers the reviewer's sharpest question: is F1≈0.27 a property of artifacts or of a quantised 24B model? **(Risk: if a frontier model scores much higher, the claim "the information is missing from the repositories" weakens to "our extractor was weak". Pre-commit to reporting either outcome — with the robustness re-run attached, both are publishable.)** | 3.0 | low | $15–35 | not started |
| **N4** | **Semantic-diff conflict detection (WS2).** Injected-conflict design (v1 option c) gives clean ground truth: inject known version/seed/digest/hardware divergences into clean graphs, report per-type precision/recall. Answers "which divergences are catchable *before* re-running". | 2.5 | medium | free | engine built |
| **N5** | **Cross-level linkage.** Do Level-0 (metadata) and Level-1 (build) features predict Level-2 (result reproduction)? n=17, underpowered — report as exploratory with honest CIs. Only possible because the two papers are combined; neither can do it alone. | 1.5 | low | free | data exists |
| **N6** | **Taxonomy validation.** The workshop taxonomy was derived automatically. Journal version needs two independent coders and Cohen's κ. Reviewers will ask. | 1.5 | medium | free | needs 2nd coder |
| **N7** | **Selective verification cost model.** Verification is expensive; use the N1/N3 predictors to triage. Report compute saved vs coverage achieved. Fujiwara's proposed PhD anchor and the strongest scope bridge to NGC. | 2.5 | medium | free | not started |
| **N8** | **Reproducibility appendix.** Full re-run instructions; documents the exact/fuzzy matching modes; ships the corrected `results_*.json`. Appropriate for a paper on reproducibility. | 1.0 | low | free | artifact fix verified |

**Slack.** Losing any two of N2/N4/N6/N7 still leaves >45% new. N1 and N3 are
non-negotiable: N1 is the thesis, N3 is the defence against the main confound.

---

## 4. Sequencing

| Phase | Work | Duration | Gate |
|---|---|---|---|
| 0 | Commit the artifact fix; re-run both matching modes | 1 h | none |
| 1 | **N1** — done | — | — |
| 2 | **N3** (needs API budget — start procurement now), **N5** (free, immediate) | 4–6 wk | budget |
| 3 | **N2**, **N4** | 4 wk | none |
| 4 | **N6** (schedule the second coder early), **N7** | 4 wk | coder |
| 5 | Writing | 6 wk | SI opens |

Roughly 4–5 months. Comfortable if the collection opens Jan 2027; behind if it
opens right after the November conference. **Confirming that date is the highest-value
action available.**

---

## 5. Risks

1. **SI scope** — only the invited paper may be extendable. Ask now (§1).
2. **Timeline** — collection not yet open; no published deadline.
3. **Novelty perception** — mitigated by the structural rule in §1 and the thesis in §2.
4. **N3 could weaken the story** — if a frontier extractor scores much higher, the
   "metadata is missing" claim softens into "our extractor was weak". Pre-commit to
   reporting either outcome; the robustness re-run makes both publishable.
5. **N6 needs a human** — the second coder is the only component that cannot be
   done solo. Line one up early.
