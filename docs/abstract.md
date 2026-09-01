# SRAF (IJCKG 2026 full-paper draft, for review)

**Title:** SRAF: An Ontology-Grounded Knowledge Graph Framework for Auditing the
Reproducibility of Machine-Learning Research

## Abstract

Computational reproducibility remains a persistent challenge in machine-learning
research, yet it is rarely measured in a principled, standards-grounded manner.
Existing FAIR assessments target datasets rather than the executable artifacts
(code, software environments, and reported results) on which machine-learning
claims depend. We present SRAF, a Semantic Reproducibility Auditing Framework
that formulates reproducibility as an ontology-grounded measurement problem.
SRAF lifts each study into a knowledge graph based on the RDIP ontology,
combining deterministic repository parsing of dependencies, version pins,
licenses, and random seeds with large-language-model extraction of
reproducibility metadata from the paper, including methods, hyperparameters,
datasets, and reported evaluation results. On this graph we define FAIR-R, a
graded, maturity-based scoring instrument whose weights are derived from
established standards, specifically the RDA FAIR Data Maturity Model, F-UJI,
FAIR4RS, and the ML Reproducibility Checklist, and which extends FAIR with a
dedicated Reproducible dimension spanning environment, method, and data
provenance. We apply SRAF to a corpus of 96 machine-learning repositories,
reconstructing each declared environment on a containerless high-performance
computing cluster and recording a two-level outcome of dependency resolution and
full build. We find that 55.8% of repositories resolve and 52.3% build, that 26
are fully buildable, and that the presence of a software license is
significantly associated with successful reproduction (odds ratio ≈ 7, p ≈
0.025). Benchmarking three open-weight large language models against a
human-verified ground truth that is 96.9% source-grounded, we characterize the
accuracy and limitations of automated reproducibility-metadata extraction, where
the strongest open-weight model attains a headline F1 of approximately 0.27 and
extraction is most reliable for datasets and weakest for reported evaluation
results, establishing automated extraction as feasible yet a key bottleneck. We
further assess result-level reproducibility by re-executing a subset of buildable
artifacts and comparing the obtained metrics against the values claimed in their
papers. SRAF, its RDIP knowledge graph, and the
annotated corpus together constitute a reusable, standards-grounded instrument
for auditing and improving the reproducibility of computational research.

**Keywords:** knowledge graph construction; computational reproducibility; FAIR
principles; scholarly research metadata; ontology-based assessment; large
language model information extraction.

---

*Two figures remain to be finalized before camera-ready: `[best F1 ≈ 0.NN]` (RQ3
fuzzy-match headline, pending the corrected-ground-truth re-run) and the
result-level reproducibility count. All other numbers (55.8% resolve, 52.3%
build, 26 full-tier, OR ≈ 7 / p ≈ 0.025, 96.9% grounding) are from completed
runs. Em dashes removed; compound-modifier hyphens retained per standard
academic style.*
