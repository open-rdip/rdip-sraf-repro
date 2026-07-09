# Paper split and coverage of the proposal RQs

- **TPDL 2026 (accepted):** the RDIP ontology / integration profile — the *target schema*.
- **Paper A (IJCKG):** the FAIR-R instrument + the empirical reproducibility study.
- **Paper B (journal extension):** the LLM extraction benchmark (+ semantic diff, + result-level reproduction).

---

## Paper A — SRAF: the instrument + empirical finding (IJCKG)

**Main contributions**

- **A1. FAIR-R, a standards-grounded reproducibility-scoring instrument.** A graded,
  maturity-based score whose criteria and weights are derived from the RDA FAIR Data
  Maturity Model, F-UJI, FAIR4RS, and the ML Reproducibility Checklist, extending FAIR
  with a novel *Reproducible* dimension, operationalised as executable SHACL shapes.
- **A2. A large-scale environment-reconstruction study.** 96 ML repositories rebuilt on a
  containerless HPC cluster with a *version-aware*, two-level (resolve / build) outcome:
  55.8% resolve, 52.3% build, 26 fully reproducible.
- **A3. Identification of metadata predictors of reproduction failure.** Logistic analysis
  showing software-license presence is a significant predictor (OR ≈ 7.3, p ≈ 0.025), and
  the basic-vs-deep metadata asymmetry.
- **A4. Validation of the instrument against outcomes.** Evidence that the FAIR-R score
  relates to observed reproduction outcomes, plus calibration against 5 exemplary,
  independently-reproduced artifacts as high-score anchors.
- **Application:** author self-audit — score + prioritised recommendations before submission.

**Answers proposal:** RQ1 and RQ4 (objective OB3). Uses RDIP (TPDL) as its schema layer.

---

## Paper B — the extraction benchmark (journal extension)

**Main contributions**

- **B1. A reproducible, open-weights extraction pipeline (PDF → RDIP).** Multi-model,
  retrieval-augmented, served locally — no dependence on proprietary APIs.
- **B2. A human-verified benchmark for reproducibility-metadata extraction.** Gold (12) +
  silver (95), 96.9% source-grounded, with an entity-aware evaluation methodology.
- **B3. Quantification of the formalisation gap.** Extraction accuracy achievable with
  current open LLMs (best ≈ 0.27 F1), per-field breakdown (datasets strongest, reported
  results hardest), and a model-scaling comparison (8B → 14B → 24B).
- **B4. Extensions:** the semantic-diff conflict taxonomy with SHACL-based pre-execution
  detection, and result-level reproduction (re-executing buildable repos vs. claimed
  numbers).

**Answers proposal:** RQ3 and RQ2 (objectives OB4 and OB2).

---

## Coverage vs. the proposal Research Questions

| Proposal RQ | Question (short) | Covered by |
|---|---|---|
| **RQ1** | Which metadata categories significantly predict reproducibility failure, and their relative contribution? | **Paper A** (A3) |
| **RQ2** | Which configuration divergences are detectable by semantic comparison *before* re-execution? | **Paper B** (B4, semantic diff) |
| **RQ3** | How large is the formalisation gap, and what extraction accuracy is achievable with current LLMs? | **Paper B** (B1–B3) |
| **RQ4** | Is the FAIR-R completeness score statistically correlated with replication outcomes? | **Paper A** (A4) |

## Coverage vs. the proposal Objectives

| Proposal OB | Objective (short) | Covered by |
|---|---|---|
| **OB1** | Technology-agnostic semantic extraction model encoding artifacts as RDIP triples | **TPDL** (schema) + used in A & B |
| **OB2** | Taxonomy of semantically detectable divergences; SHACL conflict-detection precision/recall | **Paper B** |
| **OB3** | Whether FAIR-R predicts replication outcomes + relative dimension weights | **Paper A** |
| **OB4** | Quantify the formalisation gap; replicable LLM-extraction benchmark vs. a manual gold standard | **Paper B** |

**Takeaway:** RQ1 + RQ4 anchor the IJCKG paper (a focused "measure it, and show it matters"
story); RQ2 + RQ3 anchor the journal extension (a focused "can we build the graph
automatically, and detect conflicts" story); RQ/OB1 is the accepted ontology paper. Each
venue gets one clean contribution.
