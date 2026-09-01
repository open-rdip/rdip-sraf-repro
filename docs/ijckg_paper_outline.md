# SRAF Updates

Working title: *SRAF: An Ontology-Grounded Instrument for Auditing Computational
Reproducibility Metadata at Scale*

---

## Paper Outline

### Abstract
- The reproducibility problem is well known but has never been measured at the
  *metadata* level.
- We built SRAF, an ontology-grounded tool that turns each repository's
  reproducibility metadata into a knowledge graph and scores it.
- We ran it on 95 real ML repositories and report which metadata actually
  predict whether a project can be rebuilt.
- Contribution: a semantically-queryable instrument + the first empirical,
  variable-level evidence on reproducibility metadata.

### 1. Introduction
- Open with the *use case* (why anyone cares): before submitting a paper, an
  author uploads it and gets a reproducibility score plus concrete fixes.
- State the gap: we know reproducibility is poor, but not *which* missing
  metadata cause it.
- One-sentence description of SRAF (ontology + SHACL + scoring).
- Who benefits: journal editors (reporting rules), funders (data mandates),
  tool builders (what to fix first).
- Bullet list of contributions.

### 2. Related Work
- Provenance ontologies (PROV-O, P-PLAN): good for "who did what", too coarse
  for technical reproducibility.
- Research-object packaging (RO-Crate): focuses on portability, not on checking
  whether results actually match.
- Reproducibility platforms (Whole Tale, MLflow, DVC): store metadata as flat
  key-values, no semantic/queryable layer.
- FAIR assessment (RDA Maturity Model, F-UJI, FAIR4RS): assess *datasets*, not
  the *activities/runs* that produce results.
- LLM-assisted knowledge-graph construction: motivates our extraction pipeline.
- End with the one-paragraph gap that SRAF fills.

### 3. Background: the RDIP Ontology
- Short recap of RDIP v2.0 (our prior work) — the schema everything is built on.
- Key classes in plain terms: the study/activity, its computing environment,
  software + dependencies, random seeds, methods, datasets, evaluation results.
- Why an ontology and not a spreadsheet: shared meaning lets us compare across
  repositories and run formal checks.

### 4. The SRAF Instrument
- **4.1 Architecture** — the five layers (ingest artifacts → semantic lifting →
  knowledge graph → validation/diff → scoring/reporting), one diagram.
- **4.2 Semantic lifting** — how environment files and paper text become RDIP
  triples (parsers + LLM extraction).
- **4.3 The FAIR-R scoring model** — the graded, standards-grounded rubric
  (this is the section the scoring table below supports; emphasise it).
- **4.4 Semantic diff** — the four-conflict taxonomy (dependency version, random
  seed, image digest, hardware) detected before re-execution.

### 5. Empirical Study Design
- **5.1 Corpus** — 96 ML repositories (Dataset B), 500 paper PDFs (Dataset A),
  a 50-paper manually-annotated gold standard.
- **5.2 Measuring reproducibility** — define the outcome as *environment
  reconstruction*, measured at two levels: does the declared dependency set
  *resolve*, and does it *build*; plus a *run* test on a rich subset (compare
  obtained numbers to the paper's claimed numbers). Note the version-aware
  build (build on each repo's declared Python) as a validity control.
- **5.3 Analysis methods** — logistic regression for predictors, Spearman for
  the score-vs-outcome correlation.

### 6. Results
- **6.1 RQ1 — predictors of reconstruction failure** — which metadata
  categories predict resolve/build/run failure (with odds ratios, p-values),
  plus the artifact-placement finding (specs hidden in sub-directories).
- **6.2 RQ2 — pre-execution conflict detection** — what fraction of failures
  the four-conflict taxonomy explains.
- **6.3 RQ3 — extraction accuracy** — precision/recall of LLM extraction vs the
  gold standard, across the three models.
- **6.4 RQ4 — does FAIR-R predict outcomes** — the correlation between the
  completeness score and reconstruction, and the empirically-refined weights.

### 7. Discussion
- What the predictors mean for evidence-based reporting requirements.
- The scoring model as a *benchmark* (validated against outcomes, not just
  expert consensus) for journals/funders.
- Honest reading of any null/weak results (e.g. environment-only completeness
  not predicting reconstruction) and why that motivates the extracted dimensions.

### 8. Limitations & Threats to Validity
- Corpus skews to ML (Papers-with-Code); out-of-distribution R/bioinformatics
  set noted separately.
- Build-testing is containerless (Python-environment level), not full system
  isolation.
- LLM extraction has a known accuracy ceiling; we characterise rather than
  exceed it.
- FAIR-R weights are partly standards-derived, partly data-refined.

### 9. Conclusion & Future Work
- Restate the instrument + the empirical findings.
- Future: machine-actionable DMP integration, larger/cross-domain corpus,
  citation-based reproducibility signals.

### References

---

## Scoring: what changed and why it matters

### A. How SRAF's new scoring compares to the old one and to existing tools

| Aspect | Old SRAF FAIR-R | **New SRAF FAIR-R** | F-UJI | RDA FAIR Data Maturity Model |
|---|---|---|---|---|
| What it assesses | a research activity's metadata | a research activity's metadata | published **dataset** objects | datasets (defines indicators) |
| Where criteria come from | **invented for the project** | **RDA indicators + F-UJI metrics + FAIR4RS + ML Reproducibility Checklist** | RDA indicators | the reference indicator set itself |
| Weighting basis | **arbitrary** (0.5/0.5 within a dimension; made-up dimension weights) | **RDA priority** — Essential / Important / Useful = 3 / 2 / 1 — then refined against observed outcomes | per-metric, maturity-based | priority classes (Essential / Important / Useful) |
| Scoring granularity | **binary** present / absent | **graded** absent / partial / full (0 / 0.5 / 1.0), i.e. machine-readable+standard scores higher than bare presence | maturity levels | five maturity levels |
| Reproducibility dimension | invented criteria, no source | grounded in the **ML Reproducibility Checklist** (seeds, hyperparameters, splits, eval) + **FAIR4RS** (executability, deps, versioning) | none (dataset FAIRness only) | none (no reproducibility notion) |
| Recommendations | generic text | **prioritised** (Essential gaps first) with the points each fix recovers | yes (per metric) | not a tool |
| Validation | none | **calibrated** against reference papers + **empirically validated** against real reconstruction outcomes (RQ4) | benchmark for datasets | community consensus |
| Output | one number | number + per-dimension radar + per-criterion table + fix list | per-principle scores + report | n/a |

### B. Which standard grounds each FAIR-R dimension (no longer invented)

| FAIR-R dimension | Grounded in |
|---|---|
| Findable | RDA-F1/F2/F3 · F-UJI FsF-F1/F2/F3 |
| Accessible | RDA-A1/A1.1 · F-UJI FsF-A1 |
| Interoperable | RDA-I1/I2 · F-UJI FsF-I1 |
| Reusable | RDA-R1.1/R1.2 · F-UJI FsF-R1.1 · FAIR4RS (software) |
| Reproducible (novel) | ML Reproducibility Checklist (Pineau/NeurIPS) + FAIR4RS — no RDA equivalent |

### C. What changed, and why it is meaningful

- **From made-up weights to standards-based weights.** Old: numbers like "7.5"
  were chosen by hand. New: each criterion's weight comes from its RDA priority
  class. *Why it matters:* the score is now defensible and comparable to the
  wider FAIR community instead of being one person's opinion.

- **From yes/no to graded scoring.** Old: a criterion was simply present or
  absent. New: a bare `LICENSE` file scores less than a declared SPDX licence;
  a tag scores less than a pinned digest. *Why it matters:* it rewards the
  *quality/machine-readability* of metadata, matching how F-UJI and the RDA
  maturity model actually work, and it stops every repository getting the same
  flat score.

- **From an invented "Reproducible" dimension to a literature-grounded one.**
  Old: the reproducibility criteria had no source. New: every one maps to a
  specific item in the ML Reproducibility Checklist or FAIR4RS. *Why it matters:*
  this is the *novel* part of FAIR-R, and reviewers will accept it because it is
  tied to community checklists, not asserted.

- **From asserted to validated.** Old: no evidence the score meant anything.
  New: weights are calibrated against reference papers (known-good vs known-bad)
  and the composite is tested for correlation with real reconstruction outcomes.
  *Why it matters:* FAIR-R becomes a *benchmark validated against outcomes*,
  which is a stronger basis for policy than expert consensus alone.

- **From buried SPARQL to executable SHACL shapes.** Each criterion is now a
  declarative SHACL shape with a severity tied to its priority. *Why it matters:*
  the rubric is inspectable, reusable, and standards-shaped — and it doubles as
  the recommendation engine.

> One-line summary for the slide: *the score went from "numbers we invented" to
> "weights grounded in the RDA/F-UJI standards, graded like F-UJI, with a novel
> reproducibility dimension grounded in the ML Reproducibility Checklist, and
> validated against real outcomes."*

## Models Used

- models--Qwen--Qwen2.5-14B-Instruct-GPTQ-Int8
- models--RedHatAI--Meta-Llama-3.1-8B-Instruct-quantized.w8a8
- models--RedHatAI--Mistral-Small-24B-Instruct-2501-quantized.w8a8