# Three closely related papers — and what they mean for us

Read 1 October 2026. One of the three (arXiv 2403.08345) could only be read in
summary; a re-fetch was refused by the proxy, so its author list, the DLProv
details and the released resources are **unconfirmed** and need checking.

---

## 1. The three papers

### P1 — From human experts to machines: LLM-supported ontology and KG construction
`doi.org/10.48550/arXiv.2403.08345`

A semi-automated pipeline that formulates competency questions, builds a TBox
aligned to them, constructs the KG, and evaluates with a **judge LLM** comparing
RAG answers and extracted concepts against ground truth. Demonstrated on a KG of
deep-learning methodologies extracted from scholarly publications. Concludes that
LLMs reduce human effort but a **human-in-the-loop remains necessary**.

*Unverified from the fetch:* the DLProv ontology's scope, its PROV-O reuse, the
competency questions, released code.

### P2 — Method reproducibility of deep learning in biodiversity research
`doi.org/10.7717/peerj-cs.2618`

**100 publications, 2015–2021.** Defines reproducibility variables in four
categories:

| category | variables |
|---|---|
| Resource | dataset availability, source code, open-source frameworks, model architecture |
| Methodological | software/hardware specs, methods documentation, hyperparameters |
| Randomness | weight initialisation, data shuffling, augmentation, train/test split |
| Statistical | averaging over multiple training runs, evaluation metrics |

**Two authors annotated independently.** First-pass Cohen's $\kappa$ = **0.57**;
after clarifying variable definitions they reached **complete agreement**.
About **40 minutes per publication**.

Findings: 579 of 1,000 variable assessments positive. Only one publication
reached the top reproducibility level, 22 met basic criteria. Randomness
documentation almost universally absent.

### P3 — Multi-LLM pipeline for extracting DL methodologies
`doi.org/10.7717/peerj-cs.3204` — Kommineni et al., 2025

Five open-weight models (Llama-3 70B, Llama-3.1 70B, Mixtral-8x22B,
Mixtral-8x7B, Gemma 2 9B) with RAG and a **voting classifier** over their
outputs. Evaluated against P2's human annotations on six reproducibility
variables, 464 publications (100 curated + 364 Ecological Informatics).

**Accuracy 69.5% · Precision 61.8% · Recall 89.3% · F1 67.5%.**
Best variable: model architecture (F1 0.94). Worst: source code (precision 0.13).

---

## 2. The thing we must handle before a reviewer does

**P3 reports F1 67.5%. We report entity-level F1 0.230–0.273.**

Side by side that looks like our pipeline is three times worse. It is not the
same task:

| | P3 | SRAF |
|---|---|---|
| unit | **binary presence** — "is the source code available?" | **entity extraction** — which dependency, which version, which seed value |
| output | yes / no per variable | typed RDIP instances with values |
| scoring | agreement with a yes/no human label | micro P/R/F1 over extracted items, strict and lenient matching |
| variables | 6 | 7 fields, open-valued |

Asking whether a paper *mentions* hyperparameters is a classification problem
with two possible answers. Extracting *which* hyperparameters, with values, is an
open-vocabulary extraction problem — and our own open-vocabulary result (80–82%
of claimed metric names unmatched by any alias table, stable across three model
families) is a measurement of exactly why the second is harder.

**Action:** the journal paper should cite P3 and state this distinction
explicitly, ideally with their figure and ours in one table. Left unstated, a
reviewer who knows this literature will read our numbers as weak. Stated, it
becomes evidence for the open-vocabulary ceiling — our central limiting claim.

Their per-variable spread supports it: model architecture F1 0.94 (a closed set
of names) against source-code precision 0.13 (an open judgement). Difficulty
tracks vocabulary openness in their results too.

---

## 3. What to borrow, concretely

**P2's annotation protocol is what N9 should follow.** Two independent
annotators, disagreement, definitions clarified, re-annotation to agreement. The
first-pass $\kappa$ = 0.57 is a strong empirical argument for the codebook-first
rule already in our plan: definitional disagreement dominates, and it is fixable.

Their **40 minutes per publication** is also a better effort estimate than my 20–30.
For 20 studies that is ~13 hours, not 8. Worth telling the second coder honestly,
and worth considering a smaller sample.

**P2's four categories are a ready-made external instrument for N2.** The plan
names F-UJI and FAIRshake, both oriented to published *datasets*. P2's framework
is ML-specific and built for exactly our kind of artifact. Running the variance
audit against it asks: does *their* instrument saturate on our corpus as ours
does? That is a sharper generalisation test than F-UJI can give.

**P3's voting classifier** is an alternative to our single-extractor design and a
natural comparison point for N3 — ensemble of open-weight models versus one
frontier model.

**P1's judge-LLM evaluation** is a methodological alternative to our gold
standard. We should say why we chose human-verified ground truth instead, since
P1 is the obvious "why didn't you just use an LLM judge" question.

---

## 4. Collaboration options with Dr. Sheeba, ranked

*Assuming the author connection is as it appears — verify first.*

**A. Cross-domain replication of the reproducibility profile.** They measured
biodiversity DL; we have 96 general ML repositories with build and result-level
outcomes. Applying their four-category framework to our corpus answers: is low
reproducibility a biodiversity finding or a machine-learning finding? Neither
group can answer that alone. Clean joint paper, uses data both sides already
hold, and needs no new corpus.

**B. Granularity study: presence versus extraction.** P3 establishes what binary
variable detection achieves; we establish what entity-level extraction achieves.
A joint paper on *how extraction difficulty scales with vocabulary openness*
would be novel, and both halves of the evidence already exist. This is the most
intellectually interesting option and the one neither group can publish alone.

**C. Instrument comparison (our N2).** Their framework as one of the instruments
in our variance audit. Natural co-authorship, modest scope, and it strengthens
N2 from "we tested two dataset-oriented tools" to "we tested a purpose-built ML
reproducibility framework".

**D. Ontology alignment.** If DLProv reuses PROV-O as RDIP does, a published
mapping between them is a concrete, citable artifact and a small piece of work.
Verify the DLProv details first.

**E. Annotation expertise for N9.** Lower ambition but immediately useful: their
team has run exactly this protocol and hit the definitional problem we are about
to hit. Even an hour of advice on the codebook would be worth having.

---

## 5. Risks to name honestly

**Our N3 overlaps P3.** Multi-model extraction of reproducibility information,
evaluated against human annotation, is their published contribution. N3 remains
defensible — frontier hosted models rather than open-weight ensembles, entity
extraction rather than binary classification, and the downstream re-scoring and
re-run of N1 — but we must position it against P3 rather than appear unaware of
it. If we do not cite P3, a reviewer in this area will.

**P2 did what N9 is doing, and did it first.** Two-author annotation with
inter-annotator agreement on reproducibility variables is their method. Ours
differs in substance (we are validating an LLM-generated gold standard, not
annotating from scratch), but the novelty claim for N9 should be framed as
*measurement validity for our corpus*, not as methodological innovation.

**Collaboration has a timing cost.** Our submission is 31 December. Options A, B
and C are new papers on their own timeline, not contributions to this one.
Only E, and citing P2 and P3 properly, affects the current submission. Worth
being clear about that with Dr. Sheeba so the conversation separates "what helps
the December deadline" from "what we start afterwards".
