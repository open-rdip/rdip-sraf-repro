# A code-native criterion set (n=96; 86 build-attempted)

Regenerate with `python3 analysis/code_native_criteria.py`. Companion to `criterion_validity.md` (why FAIR-R fails) and `taxonomy_restructured.md` (what actually breaks).

## 1. Do these criteria vary? (the test FAIR-R fails)

FAIR-R forfeits 57.8 of 100 points identically for every repository. A replacement criterion earns its place only if it varies here.

| Criterion | mean | sd | varies |
|---|---:|---:|:--:|
| Software licence present | 0.84 | 0.36 | yes |
| Python version declared | 0.43 | 0.50 | yes |
| Docker/OCI recipe present | 0.39 | 0.49 | yes |
| Conda environment present | 0.29 | 0.46 | yes |
| pip requirements present | 0.80 | 0.40 | yes |
| More than one environment declaration | 0.73 | 0.45 | yes |
| Environment files at repository root | 0.75 | 0.44 | yes |
| Count of environment artefacts | 3.40 | 3.06 | yes |
| Extracted metadata richness (log triples) | 4.51 | 1.46 | yes |

- **9 of 9 vary**, against 6 of 15 for FAIR-R (and only 3 of those usable). Nothing here is dead weight.

## 2. Univariate association with outcome

Spearman rho over the build-attempted set, with Benjamini-Hochberg correction across the criteria tested.


### `resolve` (events 48/86)

| Criterion | rho | p | BH q | survives |
|---|---:|---:|---:|:--:|
| Software licence present | +0.250 | 0.0203 | 0.1277 | no |
| More than one environment declaration | +0.236 | 0.0284 | 0.1277 | no |
| Python version declared | +0.213 | 0.0492 | 0.1475 | no |
| Conda environment present | +0.179 | 0.0997 | 0.2243 | no |
| pip requirements present | -0.151 | 0.1646 | 0.2963 | no |
| Count of environment artefacts | +0.139 | 0.2007 | 0.3010 | no |
| Extracted metadata richness (log triples) | -0.103 | 0.3459 | 0.3977 | no |
| Docker/OCI recipe present | +0.097 | 0.3748 | 0.3977 | no |
| Environment files at repository root | -0.092 | 0.3977 | 0.3977 | no |

### `build` (events 45/86)

| Criterion | rho | p | BH q | survives |
|---|---:|---:|---:|:--:|
| Software licence present | +0.220 | 0.0415 | 0.2444 | no |
| More than one environment declaration | +0.202 | 0.0625 | 0.2444 | no |
| Python version declared | +0.175 | 0.1077 | 0.2444 | no |
| pip requirements present | -0.174 | 0.1086 | 0.2444 | no |
| Extracted metadata richness (log triples) | -0.140 | 0.1991 | 0.3584 | no |
| Count of environment artefacts | +0.110 | 0.3138 | 0.3769 | no |
| Conda environment present | +0.109 | 0.3177 | 0.3769 | no |
| Docker/OCI recipe present | +0.105 | 0.3351 | 0.3769 | no |
| Environment files at repository root | -0.079 | 0.4673 | 0.4673 | no |

## 3. Discrimination against the incumbents

10-fold stratified CV, 20 repeats. *Scored* rows collapse the criteria into one 0-100 number using weights derived inside each training fold — that is what an instrument actually hands a reader. *Model* rows fit all criteria jointly and are an upper bound, not a deliverable.

| Outcome | Instrument | CV AUC |
|---|---|---:|
| `resolve` | FAIR-R v1 (aggregate) | 0.584 ± 0.188 |
| `resolve` | Software licence alone | 0.586 ± 0.121 |
| `resolve` | Code-native (scored, in-fold weights) | 0.622 ± 0.202 |
| `resolve` | Code-native (model, upper bound) | 0.614 ± 0.212 |
| `build` | FAIR-R v1 (aggregate) | 0.555 ± 0.181 |
| `build` | Software licence alone | 0.577 ± 0.123 |
| `build` | Code-native (scored, in-fold weights) | 0.574 ± 0.211 |
| `build` | Code-native (model, upper bound) | 0.578 ± 0.196 |

**Read this conservatively.** The gain over FAIR-R is real and consistent in direction, but modest, and the standard deviations overlap. The claim the data supports is *not* 'we built an accurate predictor'. It is: criteria chosen because they vary and because they correspond to observed failures discriminate better than a standards-derived rubric whose mass sits on criteria that never vary — and they do so while remaining deterministic, requiring no language-model extraction.

## 4. Tier B — the criteria the taxonomy says matter most

These come straight from the 16 artifact failures. **None is computable from stored data**: each needs a new static check in the build harness, so evaluating them requires a corpus re-clone (a cluster job). They are specified here so they can be implemented and then measured — not claimed as results.

| Criterion | What it checks | Why (evidence) | FAIR-R coverage |
|---|---|---|---|
| `concrete_run_command` | A documented run command with no unfilled placeholder | 7 of 16 artifact failures (the single largest mode). Static check: parse fenced code blocks in README/docs; flag /path/to, <...>, $VAR, YOUR_. | NOT COVERED by FAIR-R at all. |
| `documented_entrypoint` | Any documented way to reproduce a reported number | 4 of 16 failures. Static check: presence of an eval/test/reproduce command or script referenced from the documentation. | Only partially covered by Reproducible R2. |
| `links_resolve` | Declared checkpoint/dataset URLs return 200 | 1 of 16 failures directly (dead 404); link rot is time-dependent so this grows with artefact age. Static check: HEAD each extracted URL. | NOT COVERED by FAIR-R at all. |
| `data_obtainable_without_application` | Required data is downloadable without a gating application | 1 of 16 failures. Static check: classify dataset access statements. | Maps to Accessible/Access level, which is absent for all 96 — i.e. present in the rubric but invariant, so it cannot discriminate. |
| `repo_matches_paper` | Linked repository corresponds to the paper | 3 of 16 failures. Static check: similarity between paper title/abstract and repository description/README. | Maps to Interoperable/Related links, absent for all 96. |

Tier B is the substance of the instrument redesign: 15 of the 16 observed artifact failures map onto these five checks, and every one of them is a cheap static test. That is the paper's constructive contribution — the diagnosis says the rubric measures the wrong things; this says what the right things are and how to compute them.

## 5. Threats

- Tier A criteria are evaluated on the same 96 repositories that motivated them. Weights are derived in-fold, so the AUCs are not circular, but the *choice* of criteria is informed by this corpus. An independent held-out set is required before claiming generalisation.
- `resolve` and `build` are Level-1 outcomes. No Level-2 outcome exists to validate against: nothing in the corpus reproduced, so the criteria are validated against environment reconstruction, not result reproduction.
- Several Tier A criteria are correlated by construction (an environment file count and the individual file-type flags). The scored version handles this only crudely; a principled weighting should account for redundancy.
