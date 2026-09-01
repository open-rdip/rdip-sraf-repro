# Reference Examples — High-FAIR-R Reproducibility Artifacts

**Purpose.** These five artifacts are *construct-validity anchors* for the
SRAF FAIR-R scorer: exemplary, independently-reproduced research artifacts that
should sit at the top of the FAIR-R scale. Including them demonstrates that the
rubric's ceiling is reachable by genuinely good work — not just that poor repos
score low — and provides the "high" band for calibration.

---

## Why these, and why ReScience C

A FAIR-R score near the maximum requires an artifact to satisfy every dimension
at its highest grade:

- **Findable** — a persistent identifier (DOI), descriptive metadata, a landing page.
- **Accessible** — open access over a standard protocol, with a declared licence.
- **Interoperable** — machine-readable metadata and typed links between the
  paper, its code, and its data.
- **Reusable** — an open software licence, a versioned/citable code release, and
  community formats.
- **Reproducible** — a pinned computational environment, declared random seeds,
  hyperparameters and methods, and dataset identity with evaluation results.

The hardest dimension for an ordinary GitHub repository is **Interoperable**
(machine-readable knowledge representation and cross-links). This is exactly why
**ReScience C** is the ideal source: it is a peer-reviewed journal of
*computational replications* in which every accepted article was **independently
reproduced by reviewers** before publication, and every artifact is archived on
**Zenodo with a DOI** (which emits DataCite/JSON-LD metadata and related-identifier
links), alongside open-licensed code. In other words, these artifacts were
*built* to be findable, accessible, interoperable, reusable, and reproducible.

---

## The five reference artifacts

| ID | Artifact | Venue | Article DOI | Code | Data |
|----|----------|-------|-------------|------|------|
| ref001 | **[Re] Network Deconvolution** — Obadage, Thennakoon, Rajtmajer & Wu (2025) | ReScience C 10(1)#4 | [10.5281/zenodo.15321683](https://doi.org/10.5281/zenodo.15321683) | [github.com/lamps-lab/rep-network-deconvolution](https://github.com/lamps-lab/rep-network-deconvolution) | ImageNet (ILSVRC, Kaggle) |
| ref002 | **Learning with Noisy Labels [Re]visited** — Hudovernik, Rot, Vovk, Škodnik & Zajc (2026) | ReScience C 11(1)#2 | [10.5281/zenodo.18401497](https://doi.org/10.5281/zenodo.18401497) | [github.com/KlemenVovk/noisy-labels](https://github.com/KlemenVovk/noisy-labels) | CIFAR-10/100 (cited) |
| ref003 | **[Re] When Does Label Smoothing Help?** — Wagner, Kurowski, Holländer & Uelwer (2025) | ReScience C 10(1)#1 | [10.5281/zenodo.14953654](https://doi.org/10.5281/zenodo.14953654) | [github.com/sdwagner/re-labelsmoothing](https://github.com/sdwagner/re-labelsmoothing) | CIFAR (linked) |
| ref004 | **[Re] BiRT: Bio-inspired Replay in Vision Transformers for Continual Learning** — Maheshwari (2025) | ReScience C 10(1)#2 | [10.5281/zenodo.14964875](https://doi.org/10.5281/zenodo.14964875) | [github.com/disha101003/ReScience](https://github.com/disha101003/ReScience) | CIFAR |
| ref005 | **[Re] Learning Fair Graph Representations via Automated Data Augmentations** — Belitsky, Laitenberger, Sheremet & Belkacemi (2025) | ReScience C 10(1)#6 | [10.5281/zenodo.16374814](https://doi.org/10.5281/zenodo.16374814) | [Zenodo 10.5281/zenodo.13834566](https://doi.org/10.5281/zenodo.13834566) | [Zenodo 10.5281/zenodo.13837423](https://doi.org/10.5281/zenodo.13837423) |

### ref001 — [Re] Network Deconvolution
A reproduction of the "Network Deconvolution" image-classification method.
Computer-vision/ML, Python. Strong on every dimension: Zenodo article DOI,
open GitHub code, and a well-known benchmark dataset (ImageNet). A good general
deep-learning exemplar.

### ref002 — Learning with Noisy Labels [Re]visited
A 2026 replication revisiting learning-with-noisy-labels methods, deep learning
in Python. Clean GitHub release plus a Zenodo-archived article DOI.

### ref003 — [Re] When Does Label Smoothing Help?
Reproduces a classic neural-network training study. Reports the comparison
metrics against the original numbers (directly exercising the Reproducible
data/evaluation cells) and links its CIFAR data.

### ref004 — [Re] BiRT: Bio-inspired Replay in Vision Transformers
A continual-learning / vision-transformer reproduction on CIFAR. Note: the code
lives in a personal `ReScience` repository — confirm the software licence when
lifting it.

### ref005 — [Re] Learning Fair Graph Representations (strongest FAIR profile)
Graph deep learning. **The best exemplar of all five**: it has *separate DOIs
for the article, the code, and the data*. That tri-part DOI linkage is exactly
the machine-readable, cross-referenced structure that satisfies the
**Interoperable** "related links" criterion which ordinary repositories miss —
so this artifact should score at or very near the maximum. (Its code is
Zenodo-archived as a citable snapshot rather than a live git URL.)

---

## How each maps to the FAIR-R dimensions

| Dimension | What it needs | Why these artifacts satisfy it |
|-----------|---------------|--------------------------------|
| **Findable** | DOI, descriptive metadata, landing page | Every artifact has a Zenodo article DOI with full DataCite metadata and a landing page. |
| **Accessible** | open protocol + licence | Platinum open-access journal; code openly licensed; retrieved over HTTPS. |
| **Interoperable** | machine-readable metadata, typed links | Zenodo emits DataCite/JSON-LD and related-identifier links (article↔code↔data); strongest for **ref005**. |
| **Reusable** | software licence, versioned release, community formats | Open-licensed code, citable/versioned Zenodo releases, standard Python project layout. |
| **Reproducible** | pinned env, seeds, methods, data + results | By design — ReScience reproductions report methods, hyperparameters, seeds, and evaluation results vs. the original; the environment pinning is confirmed at lift. |

---

## Honest caveat

These are real artifacts, not curated perfect scores. The exact FAIR-R number is
produced by **lifting each into the RDIP knowledge graph** (build-harness repo
parse + paper extraction) and running the scorer. Expect scores in the **high
80s–90s** rather than a flat 100: one or two cells — a pinned Docker digest, or
an *explicitly declared* random seed — are only confirmed once the repository is
parsed. This is the correct, defensible framing for a paper: exemplary artifacts
land at the top of the scale, validating the rubric's upper range, while the
remaining gap to 100 is itself informative.

---

## How they are used in SRAF

- Registered as the **`high` band** of the calibration set
  (`calibration/reference_set.yaml`) — the rubric must rank these above the
  low-band repos (construct validity, RQ-calibration).
- Ready to lift via `validation/reference_repos.csv` (same format as the main
  corpus list), then scored with the FAIR-R scorer.

---

## References

- ReScience C — A Journal for Reproducible Replications in Computational Science.
  https://rescience.github.io/
- Obadage, R. R., Thennakoon, K., Rajtmajer, S. M., & Wu, J. (2025). *[Re] Network
  Deconvolution.* ReScience C 10(1), #4. https://doi.org/10.5281/zenodo.15321683
- Hudovernik, V., Rot, Ž., Vovk, K., Škodnik, L., & Zajc, L. Č. (2026). *Learning
  with Noisy Labels [Re]visited.* ReScience C 11(1), #2.
  https://doi.org/10.5281/zenodo.18401497
- Wagner, S. D., Kurowski, Y. P., Holländer, L. M., & Uelwer, T. (2025). *[Re] When
  Does Label Smoothing Help?* ReScience C 10(1), #1.
  https://doi.org/10.5281/zenodo.14953654
- Maheshwari, D. (2025). *[Re] BiRT: Bio-inspired Replay in Vision Transformers for
  Continual Learning.* ReScience C 10(1), #2.
  https://doi.org/10.5281/zenodo.14964875
- Belitsky, M., Laitenberger, F., Sheremet, D., & Belkacemi, N. (2025). *[Re]
  Learning Fair Graph Representations via Automated Data Augmentations.* ReScience
  C 10(1), #6. https://doi.org/10.5281/zenodo.16374814 ·
  Code https://doi.org/10.5281/zenodo.13834566 ·
  Data https://doi.org/10.5281/zenodo.13837423
