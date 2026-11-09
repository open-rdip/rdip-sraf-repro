# SRAF proposal — status against what was promised

Checked against the repository on 1 October 2026, not against memory.
Status marks: **done** · **partial** · **not started** · **diverged**

---

## 1. Research questions

| | Question | Status | Evidence |
|---|---|---|---|
| **RQ1** | Which metadata categories predict reproducibility failure? | **done**, with a negative result | N1: 57.8 of 100 points invariant across all 96 repositories; 9 of 15 criteria have zero variance. Software licence is the only criterion surviving FDR for both outcomes. |
| **RQ2** | Which divergences are detectable before re-execution, and how do they relate to failure rate? | **diverged** — see §4 | Detection is built and evaluated (C1: recall 1.000, 0/103 false positives). The *relationship to failure rate* is not answerable: no study reached re-execution. |
| **RQ3** | What extraction accuracy is achievable against a gold standard? | **done** | Three open-weight models, entity-level F1 0.230 / 0.223 / 0.273 against the gold standard. N3 extends this to frontier models. |
| **RQ4** | Does a composite completeness score predict replication outcomes? | **done**, negative | ρ = 0.10–0.16, not significant. N1 explains *why*, which is the stronger result. |

**The headline finding is a null, and the proposal did not anticipate that.** §7 reads
"If the FAIR-R scoring model demonstrates statistically significant predictive
validity…". It does not. The project's value now rests on N1's diagnosis — the
instrument was built for curated data archives and applied to working code
repositories where most of its questions are automatically "no" — rather than on
a validated benchmark. That is a defensible and more interesting outcome, but it
is a different claim from the one proposed, and it should be stated as such
rather than allowed to look like a shortfall.

---

## 2. Objectives

| | Objective | Status |
|---|---|---|
| **OB1** | Technology-agnostic semantic extraction into RDIP triples | **done** — `lifter/`, `rag_pipeline/`, 96 repositories lifted |
| **OB2** | Taxonomy of pre-execution divergences; precision/recall against CI-verified build ground truth | **partial / diverged** — taxonomy and detector built and measured, but against *planted* conflicts, not against build outcomes |
| **OB3** | Is the multidimensional score a significant predictor, and what is each dimension's weight? | **done**, negative; re-weighting does not rescue it (a single licence bit predicts as well as the whole instrument) |
| **OB4** | Quantify the formalisation gap; replicable LLM extraction benchmark | **done** — benchmark exists and is released |

---

## 3. Phases

### Phase I — Corpus construction

| Promised | Actual | |
|---|---|---|
| 96 repositories from Papers with Code, stratified | 96 | **done** |
| Dataset A: 500 paper PDFs | 500 records in `dataset_a_kg_population.json` | **done** |
| Gold standard: **50** papers manually annotated | **108** (12 gold + 96 silver) | **exceeded in count** |

**But the gold standard has a defect the proposal did not foresee.** All 108
files record `_verified_by: "First Author"`. Annotation volume more than doubled
the commitment; annotation *rigour* has a single-annotator problem that every
reported F1 depends on. N9 addresses it; the second coder is now secured.

### Phase II — Pipeline deployment

Environment lifting, RAG extraction, KG storage: **done**. One subgraph per
study, 96 studies, RDIP v2.1.0.

### Phase III — Auditing and evaluation

| Promised | Actual | |
|---|---|---|
| SHACL engine, violation sets, completeness profiles | built, run over 96 | **done** |
| Semantic diff: original vs reproduction attempt | **no reproduction graphs exist** | **diverged** |
| Build ground truth for all 96 via **automated CI pipeline testing** | 96 via Slurm + Apptainer harness | **done, different mechanism** |
| Result ground truth on a **30-repository** subsample, tolerance **0.5%** | 26 eligible, 17 attempted, tolerance **5% relative or 0.01 absolute** | **diverged** |

### Phase IV — Analysis

Firth penalised regression, BH-FDR, Bonferroni, cross-validated AUC, FAIR-R v1
vs v2 vs licence-only: **done**. The three-category evidence classification the
proposal specified (confirmed present / confirmed absent / present-but-not-
extracted) is **partial** — the variance audit does the equivalent job, but the
explicit three-way split is not reported as such and should be, since the
proposal called it "essential for the validity of the RQ1 and RQ4 findings".

---

## 4. The four divergences to put in front of the committee

**1. The semantic diff compares something else than proposed.**
RQ2 and OB2 assume a reproduction attempt exists to diff against the original.
None does — 17 attempted, 0 ran to a number. The implemented diff compares the
**paper against the repository**, which is the comparison the corpus can support.
Conflict types changed accordingly: proposed *dependency version, absent seed,
image digest, hardware change*; implemented *dataset, hyperparameter, metric,
dependency, seed*. Digest and hardware remain only on the unused
original-vs-reproduction path.

This is a reasonable pivot — the paper↔repo diff is arguably a more useful
artifact than the original one — but it is a change of research question, not an
implementation detail.

**2. Tolerance is 5%, not 0.5%** — a tenfold relaxation, plus a 0.01 absolute
floor the proposal did not have. Justified in the workshop paper (the corpus
spans accuracy, mAP, mIoU, panoptic quality and perplexity; a relative test is
unstable near zero), but it is a loosening of the success criterion and will be
noticed.

**3. Build ground truth is not CI.** The proposal says "automated CI pipeline
testing"; the implementation is a Slurm and Apptainer harness on ASL. Functionally
equivalent and arguably more controlled, but the wording should be corrected
rather than left to look like CI was used.

**4. The result-reproduction subsample is 26 eligible / 17 attempted, not 30.**
The reduction is principled — 70 repositories never built, and 9 of the 26 were
excluded as out-of-scale, hardware-bound or repo/paper mismatched — but the
proposal promised 30 and the delivered number is lower.

---

## 5. Not started

| Item | Where it sits now |
|---|---|
| **Ontological DMP model** (novelty claim 3) | `lifter/parsers/dmp_parser.py` exists; the *ontological model* is not built. The proposal already positions this as forward-looking rather than empirically evaluated, so it is consistent — but it is a named novelty contribution with nothing published behind it yet. |
| Reproducibility dashboard | `dashboard/app.py` and `fair_r_scorer.py` exist; completeness and the recommendation engine unverified. |
| Violation and Recommendation Log with remediation steps | not built. The taxonomy restructure covers the analysis half; the per-criterion remediation output does not exist. |

---

## 6. Delivered beyond the proposal

Worth listing, because several are stronger than what was promised:

- **Result-level reproduction funnel and failure taxonomy** — an entire second paper (RDM-KG 2026, accepted). The proposal treated result reproduction as one Phase III bullet.
- **`rdip:ExecutionRecipe`** — ontology extension, RDIP v2.1.0, released and resolvable.
- **Tier-B static checks** — 96-repository sweep, rules v4.
- **Deterministic repo-side experimental facts** — datasets, hyperparameters, computable metrics, seeds; FACTS_VERSION 9 with full sweep provenance.
- **Cross-extractor control** — conflict counts swing five-fold between models on identical repositories, which quantifies the LLM confound the proposal only flagged as a risk.
- **Open-vocabulary ceiling** — 80–82% of claimed metric names unmatched, stable across three model families. A limit on what this class of tooling can achieve.
- **Injected-conflict evaluation** (C1) — exact ground truth for the detector.

---

## 7. What this means for the thesis narrative

The proposal framed success as *"if FAIR-R predicts, it becomes the first
empirically grounded benchmark for reproducibility metadata requirements"*.

It does not predict. The honest and stronger reframing, already adopted in the
journal extension, is: **reproducibility scores measure how well a study is
described, not whether it reproduces** — and the project now has the variance
audit, the cross-extractor control and the open-vocabulary result to explain
*why*, which a successful prediction would never have produced.

That is a benchmark-setting finding of a different kind: it tells journals and
funders that completeness scoring of the FAIR kind cannot carry the policy weight
the field has been assuming. Worth stating plainly to the committee rather than
presenting the null as a partial result.
