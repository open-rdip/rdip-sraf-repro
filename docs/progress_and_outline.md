# SRAF — Progress Update & Paper Outline

---

## SLIDE: Progress Since Last Update

**SRAF: Semantic Reproducibility Auditing Framework** — building and evaluating
an ontology-grounded instrument that measures the reproducibility of ML research.

**Infrastructure & corpus**
- Containerless HPC pipeline operational (conda env + standalone triplestore; single-job Slurm harness).
- Corpus assembled: **96 ML repositories** (95 with retrievable papers).
- Three open-weight extraction models cached and served under the 200 GB budget.

**Method components built**
- **RDIP knowledge-graph lift**: repositories + papers into a typed KG.
- **FAIR-R scoring redesigned**: graded (maturity-based), standards-grounded
  (RDA FAIR Data Maturity Model, F-UJI, FAIR4RS, ML Reproducibility Checklist),
  with SHACL validation and a semantic-diff conflict detector.
- **Multi-model RAG extraction** (paper → RDIP metadata); all 3 models run on 95 papers.

**Ground truth**
- Human-verified **gold (12)** + **silver (95)** annotations.
- Independent verification harness: **96.9% of entities grounded** in source;
  identified and corrected the defects found.

**Results so far**
- **Environment reconstruction:** 55.8% of repos resolve, 52.3% build; 26 fully buildable.
- **RQ1 (predictors):** software **license presence significantly predicts**
  reproduction (odds ratio ≈ 7, p ≈ 0.025).
- **RQ3 (extraction accuracy):** best open model F1 ≈ 0.27; strongest on datasets,
  weakest on reported results — extraction is feasible but a clear bottleneck.
- **Reference set:** 5 exemplary high-FAIR artifacts curated as calibration anchors.
- **Abstract + title drafted and submitted.**

**In progress / next**
- **RQ4:** does the FAIR-R score predict reproducibility (analysis chain wired).
- **Result-level reproduction:** re-run buildable repos vs. claimed numbers (scaffolded).
- **Full paper draft.**

---

## Paper Outline (headings + subheadings)

**1. Introduction**
- 1.1 The computational reproducibility problem in ML
- 1.2 The measurement gap: FAIR targets datasets, not executable artifacts
- 1.3 Motivating use case: pre-submission reproducibility self-audit
- 1.4 Contributions

**2. Background and Related Work**
- 2.1 Empirical studies of computational reproducibility
- 2.2 FAIR principles and assessment tools (RDA Maturity Model, F-UJI)
- 2.3 FAIR for research software (FAIR4RS) and ML reproducibility checklists
- 2.4 Knowledge graphs for scholarly and research metadata

**3. The RDIP Ontology**
- 3.1 Design goals and scope
- 3.2 Core classes (datasets, software, methods, parameters, seeds, environment, results)
- 3.3 Activities, provenance, and relations
- 3.4 Modeling reproducibility as typed metadata

**4. The SRAF Framework**
- 4.1 Architecture overview
- 4.2 Knowledge-graph construction: deterministic repository parsing
- 4.3 Knowledge-graph construction: LLM extraction from papers
- 4.4 FAIR-R scoring: graded, standards-grounded, priority-weighted
- 4.5 SHACL validation and semantic-diff conflict detection

**5. Corpus and Ground Truth**
- 5.1 Corpus construction (96 ML repositories)
- 5.2 Annotation protocol (gold / silver)
- 5.3 Ground-truth verification and quality

**6. Experiments and Results**
- 6.1 Research questions
- 6.2 Environment reconstruction: the resolve → build → run funnel
- 6.3 RQ1: which metadata predicts reproduction failure
- 6.4 RQ2: semantic conflicts between studies (diff)
- 6.5 RQ3: accuracy of automated metadata extraction (model comparison)
- 6.6 RQ4: does the FAIR-R score predict reproducibility
- 6.7 Result-level reproducibility on a buildable subset

**7. Discussion**
- 7.1 Implications for authors, reviewers, and venues
- 7.2 Limitations
- 7.3 Threats to validity

**8. Conclusion and Future Work**

**Appendices**
- A. FAIR-R rubric and standards mapping
- B. RDIP ontology specification
- C. Reproducibility of this study (artifacts, prompts, configurations)
