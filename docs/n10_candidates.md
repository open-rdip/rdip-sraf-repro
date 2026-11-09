# N10 — candidate shortlist

**Unverified.** These titles came from a summarising fetch of
<https://rescience.github.io/read/>, not from the page's markup. Confirm each
against the site before entering it in the CSV; treat this as a starting point
that saves searching, not as data.

ACM is dropped: badge filtering needs a subscription, and ACM badging is
concentrated in systems and PL, so it would not have matched an ML corpus
anyway. ReScience has ample supply — Volume 9 Issue 2 (MLRC 2022) alone has 45
articles, Volume 8 has 54, Volume 7 has 34.

## Supply by volume

| volume | year | articles | note |
|---|---|---|---|
| 11 | 2026 | 2 | |
| 10 | 2025 | 7 | |
| 9 | 2023–24 | 51 | Issue 2 = 45 from MLRC 2022 |
| 8 | 2022 | 54 | |
| 7 | 2021 | 34 | |

## Candidates from MLRC 2022 (Volume 9, Issue 2)

Each is a `[Re]` — a successful replication. **The paper you enter in the CSV is
the one being replicated, not the replication report.**

| # | replication report | original work |
|---|---|---|
| 1 | Exact Feature Distribution Matching for Arbitrary Style Transfer and Domain Generalization | EFDM |
| 2 | End-to-end Algorithm Synthesis with Recurrent Networks | deep thinking / algorithmic extrapolation |
| 3 | Label-Free Explainability for Unsupervised Models | label-free XAI |
| 4 | Exploring the Representation of Word Meanings in Context | word homonymy representation |
| 5 | Intriguing Properties of Contrastive Losses | SimCLR / contrastive learning |
| 6 | Bandit Theory and Thompson Sampling-guided Directed Evolution | sequence optimisation |
| 7 | Hypergraph-Induced Semantic Tuplet Loss for Deep Metric Learning | HIST |
| 8 | Easy Bayesian Transfer Learning with Informative Priors | Bayesian transfer learning |
| 9 | On the Reproducibility of CartoonX | CartoonX |
| 10 | Reproducibility Study of "Label-Free Explainability…" | label-free XAI *(dup of 3)* |
| 11 | FOCUS: Flexible Optimizable Counterfactual Explanations for Tree Ensembles | FOCUS |
| 12 | Fairness Guarantees under Demographic Shift | fairness under shift |
| 13 | DialSummEval | summarisation metric evaluation |
| 14 | On the Reproducibility of "FairCal" | FairCal |
| 15 | Reproducibility Study: Label-Free Explainability | label-free XAI *(dup of 3)* |
| 16 | Explaining Deep CNNs via Latent Visual-Semantic Filter Attention | CNN explainability |
| 17 | Quantifying Societal Bias Amplification in Image Captioning | caption bias |
| 18 | On the reproducibility of "CrossWalk" | CrossWalk |
| 19 | Reproducing FairCal | FairCal *(dup of 14)* |
| 20 | Reproducibility Study of "CartoonX" | CartoonX *(dup of 9)* |

## Two things this list already tells you

**Deduplicate by original paper, not by report.** Label-free XAI appears three
times, CartoonX twice, FairCal twice. Twenty reports here are roughly fifteen
distinct originals. One CSV row per original.

**The duplicates are your best candidates.** A paper reproduced independently by
three separate teams is far stronger evidence than one reproduced once — and
where the teams disagree, that is interesting in its own right. Prefer the
multiply-replicated originals when choosing which fifteen to twenty to keep.

## Still required per candidate

The check from the sourcing guide has not been done for any of these:

> Does the report say the replicators **used the original authors' code**?

MLRC teams frequently re-implement because the original code was unusable, and a
`[Re]` on such a report reproduces the *result* while saying nothing about the
*artifact*. SRAF audits the authors' repository, so those rows would make the
stratum measure method soundness instead of artifact quality. Open each report
and look for "we used the authors' implementation" versus "we re-implemented".

## Domain note

This cohort skews heavily toward explainability and fairness. Your main corpus is
broader. Record the imbalance in `matched_to` and consider drawing some rows from
Volumes 7, 8 and 10 to spread the domains rather than taking all twenty from one
issue.
