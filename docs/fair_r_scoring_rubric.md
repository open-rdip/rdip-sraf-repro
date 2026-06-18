# FAIR-R Scoring — Standards Grounding & Proposed Rubric

Purpose: replace the ad-hoc FAIR-R weights (identifier = 7.5, etc.) with a rubric
**derived from and benchmarked against published standards**, as the advisors
required. This document (1) summarises the standards, (2) defines a principled
weighting and graded-scoring scheme, (3) proposes the rubric, and (4) gives a
calibration/validation plan. It is the design step that gates further scoring
automation.

---

## 1. The standards we ground in

**RDA FAIR Data Maturity Model** (Bahim et al. 2020; FAIR DMM WG 2020). The
authoritative community reference: **41 indicators** across Findable, Accessible,
Interoperable, Reusable, each assigned a **priority — Essential / Important /
Useful** — and organised into **five maturity levels**. The WG states the
indicators are "the foundation on top of which evaluation methodologies can be
built." → We take the **indicator set and the priority classes as our weighting
basis** (Essential > Important > Useful), instead of equal 0.5/0.5 weights.

**F-UJI** (Devaraju & Huber 2022; FAIRsFAIR / Horizon 2020). The reference
*automated* implementation. It defines **17 core metrics** derived from the RDA
indicators, in a **hierarchical model: FAIR principle → metric → practical
test(s)**, and aggregates test scores to report FAIRness "as a whole, by
principle, or by metric." Crucially, F-UJI publishes **scoring schemes with
justifications** for each test, and scores by **maturity level**, not binary
presence. → We mirror F-UJI's **principle→criterion→test hierarchy**, its
**graded (maturity) scoring**, and use it as our **benchmark** for the F/A/I/R
dimensions.

**FAIR4RS** (Chue Hong et al. 2022, RDA Recommendation). Extends FAIR to research
*software*, addressing what datasets-only models miss: **executability, composite
nature (dependencies), and versioning**. → Grounds our software/code criteria
(commit/version pinning, dependency versions, repository identifier, software
license) — appropriate because SRAF assesses code repositories, not just datasets.

**ML Reproducibility Checklist** (Pineau et al. 2020/2021; NeurIPS Reproducibility
Program). The community standard for *computational* reproducibility, with items
for: model/algorithm description & assumptions; **hyperparameters** (range,
selection method, final values); **data** (train/val/test splits, exclusions,
preprocessing); **code** (training + evaluation); and **statistical reporting**
(central tendency, variance/error bars, number of runs, **random seeds**). →
Grounds the **novel Reproducible dimension**, which has no RDA equivalent.

---

## 2. Principled weighting (replaces the invented weights)

Two levels of weighting, each justified rather than asserted:

1. **Within a dimension — by RDA priority.** Each criterion inherits its RDA
   indicator's priority. Numeric mapping: **Essential = 3, Important = 2, Useful =
   1**. A criterion's share of its dimension = its priority ÷ sum of priorities in
   that dimension. Priorities are **confirmed against the RDA spec** (FAIR Data
   Maturity Model v0.90, Zenodo 3909563): F1/F2/F3 Essential; A1-02M Essential,
   A1-01M Important; A1.1 Essential; I1/I2/I3 Important; R1.1 Essential, R1.2
   Important, R1.3 Essential.

2. **Across dimensions — grounded, then empirically validated.** Keep the F/A/I/R
   weights aligned to RDA emphasis, and justify the Reproducible weight (0.30) by
   the reproducibility literature (environment + method + data are the dominant
   failure causes). **Then refine the weights empirically** from observed
   outcomes via the RQ4 logistic regression — i.e., let the data tell us each
   dimension's true predictive contribution. This dual basis (standards +
   observed validity) is the strongest answer to "why these weights."

## 3. Graded scoring instead of binary present/absent

F-UJI and the RDA model score by **maturity**, not a yes/no. We adopt a 3-level
scale per criterion, which also fixes our flat-score problem:

| Level | Meaning | Score |
|---|---|---|
| 0 | absent | 0 |
| 1 | present but as free text / not standardised | 0.5 × weight |
| 2 | present, machine-readable, standard vocabulary (e.g. SPDX licence, PID scheme) | 1.0 × weight |

This rewards *quality* of metadata (a raw `LICENSE` file vs. a declared SPDX
identifier), matching F-UJI's licence/PID tests.

---

## 4. Proposed FAIR-R rubric (criteria → standard → priority)

Priorities below are **confirmed against the RDA spec** (FAIR Data Maturity Model
v0.90). "FsF-*" = the corresponding F-UJI metric to benchmark against.

### Findable (RDA-aligned)
| Criterion | Maps to | Priority |
|---|---|---|
| Persistent identifier (PID scheme + resolves) | RDA-F1-01M / FsF-F1-01D, F1-02D | Essential |
| Descriptive core metadata (creator, title, date, …) | RDA-F2-01M / FsF-F2-01M | Essential |
| Metadata includes the data identifier / landing page | RDA-F3-01M / FsF-F3-01M | Essential |

### Accessible
| Criterion | Maps to | Priority |
|---|---|---|
| Access level declared (controlled vocab) | RDA-A1-01M / FsF-A1-01M | Important |
| Standard access protocol (http/s, etc.) | RDA-A1-02M / FsF-A1-02M/03D | Essential |
| Data licence (SPDX) | RDA-A1.1 / FsF-R1.1-01M | Essential |

### Interoperable
| Criterion | Maps to | Priority |
|---|---|---|
| Formal knowledge representation (RDF/JSON-LD) | RDA-I1-01M / FsF-I1-01M | Important |
| Uses shared semantic resources / vocabularies | RDA-I1-02M / FsF-I1-02M | Important |
| Links to related entities (PROV-O / DataCite relations) | RDA-I3-01M / FsF-I3-01M | Important |

### Reusable
| Criterion | Maps to | Priority |
|---|---|---|
| Software licence (SPDX) | RDA-R1.1-01M / FsF-R1.1-01M; FAIR4RS R | Essential |
| Provenance: commit hash + versioning | RDA-R1.2-01M / FsF-R1.2-01M; FAIR4RS | Important |
| Community metadata / format standard | RDA-R1.3-01M / FsF-R1.3-01M | Essential |

### Reproducible (novel — grounded in ML Repro Checklist + FAIR4RS)
| Sub-dimension | Criterion | Grounded in |
|---|---|---|
| R1 Computational environment | pinned image digest / dependency versions; hardware + CUDA | Checklist (code/env); FAIR4RS (executability, deps, versioning) |
| R2 Methodological transparency | methods/algorithm; hyperparameters + selection; **random seed** | Checklist (algorithm, hyperparameters, seeds) |
| R3 Data provenance | dataset identity; train/val/test split; preprocessing; **evaluation result** | Checklist (data, splits, preprocessing, statistical reporting) |

This is the key fix for the advisors' concern: every Reproducible criterion now
cites a specific, published checklist item rather than being invented.

---

## 5. Calibration & validation plan

1. **Reference-paper calibration (construct validity).** Assemble a small
   reference set: papers that *should* score high — e.g. ACM "Artifact Evaluated
   / Reproduced" badged papers, ML Reproducibility Challenge successes — and
   papers that should score low. Verify the rubric reproduces the expected
   ordering; adjust graded-level thresholds until it does.
2. **Benchmark against F-UJI.** For the F/A/I/R criteria that overlap with
   datasets, run F-UJI on the same objects and compare per-dimension scores —
   establishes comparability with the standard tool.
3. **Empirical weight validation (criterion validity).** Fit the RQ4 logistic
   regression of reproduction outcome on the dimension scores; report each
   dimension's coefficient and refine cross-dimension weights toward observed
   predictive contribution. Document weights as *standards-grounded and
   outcome-validated*.

---

## 6. What changes in code

- `dashboard/fair_r_scorer.py`: replace binary `ASK` with the 3-level graded
  check; replace equal 0.5 weights with the RDA-priority weights; add the new
  F/A/I/R criteria (descriptive metadata, access protocol, semantic resources).
- ~~Confirm each criterion's **RDA priority** against the spec table (Zenodo
  3909563) and fill the priority column exactly.~~ **Done** — priorities verified
  against the spec PDF; three first-pass mismatches corrected (landing page
  Important→Essential, related links Useful→Important, community standard
  Useful→Essential).
- Express each criterion as an executable **SHACL shape** (as the proposal
  promises) rather than only SPARQL ASK.
- Keep the cross-dimension weights configurable so RQ4 can refine them.

---

## References (sources)

- FAIR Data Maturity Model Working Group (2020). *FAIR Data Maturity Model:
  Specification and Guidelines.* RDA. https://doi.org/10.15497/rda00050 ·
  Zenodo https://zenodo.org/record/3909563
- Bahim, C. et al. (2020). *The FAIR Data Maturity Model: An Approach to
  Harmonise FAIR Assessments.* Data Science Journal 19:41.
  https://datascience.codata.org/articles/10.5334/dsj-2020-041
- Devaraju, A. & Huber, R. (2022). *An automated solution for measuring the
  progress toward FAIR research data (F-UJI).* Patterns / FAIRsFAIR.
  Methods: https://www.f-uji.net/index.php?action=methods · Code:
  https://github.com/pangaea-data-publisher/fuji
- Chue Hong, N. P. et al. (2022). *FAIR Principles for Research Software (FAIR4RS
  Principles) v1.0.* RDA Recommendation. https://doi.org/10.15497/RDA00068 ·
  https://zenodo.org/records/6623556
- Pineau, J. et al. (2020/2021). *Improving Reproducibility in Machine Learning
  Research (NeurIPS 2019 Reproducibility Program).* arXiv:2003.12206 ·
  Checklist v2.0: https://www.cs.mcgill.ca/~jpineau/ReproducibilityChecklist.pdf
