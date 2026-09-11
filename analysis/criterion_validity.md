# Criterion-level predictive validity of FAIR-R (n=96)

Phase-1 analysis for the New Generation Computing extension. Regenerate with `python3 analysis/criterion_validity.py`.

_Reconstruction check: max |sum(criteria) - stored total| = 0.000._


## Q1 — Variance audit: how much of the instrument actually varies?

| dimension | criterion | max pts | levels observed | mean earned | sd | varies |
|---|---|---:|---|---:|---:|:--:|
| Findable | Persistent identifier | 5.00 | partial×95, full×1 | 2.53 | 0.26 | yes |
| Findable | Descriptive metadata | 5.00 | full×95, absent×1 | 4.95 | 0.51 | yes |
| Findable | Landing page | 5.00 | absent×96 | 0.00 | 0.00 | **no** |
| Accessible | Access protocol | 5.62 | full×96 | 5.62 | 0.00 | **no** |
| Accessible | Data licence | 5.62 | absent×96 | 0.00 | 0.00 | **no** |
| Accessible | Access level | 3.75 | absent×96 | 0.00 | 0.00 | **no** |
| Interoperable | Method declared | 6.67 | full×94, absent×2 | 6.53 | 0.96 | yes |
| Interoperable | Workflow language | 6.67 | absent×96 | 0.00 | 0.00 | **no** |
| Interoperable | Related links | 6.67 | absent×96 | 0.00 | 0.00 | **no** |
| Reusable | Software licence | 7.50 | full×77, absent×15, partial×4 | 6.17 | 2.77 | yes |
| Reusable | Commit + versioning | 5.00 | full×96 | 5.00 | 0.00 | **no** |
| Reusable | Community standard | 7.50 | absent×96 | 0.00 | 0.00 | **no** |
| Reproducible | Computational environment (R1) | 12.00 | partial×96 | 6.00 | 0.00 | **no** |
| Reproducible | Methodological transparency (R2) | 9.00 | partial×84, full×11, absent×1 | 4.97 | 1.53 | yes |
| Reproducible | Data provenance (R3) | 9.00 | full×75, partial×13, absent×8 | 7.64 | 2.78 | yes |

- Total rubric budget: **100.0** points across 15 criteria.
- **Invariant on this corpus: 57.8 points (57.8%)** — identical for all 96 repositories, so they cannot contribute to discrimination.
- Criteria that vary at all: **6 of 15** (Persistent identifier, Descriptive metadata, Method declared, Software licence, Methodological transparency (R2), Data provenance (R3)).
- Live (discriminating) budget: **42.2 points**. This is the ceiling on the spread of the aggregate score, and explains the tight observed distribution.

## Q2 — Which criteria predict Level-1 outcomes?

Restricted to the 86 build-attempted repositories (resolve n+=48, build n+=45).


### Outcome: `resolve_success`

| criterion | rho | raw p | BH-FDR q | Bonferroni p | survives FDR 0.05 |
|---|---:|---:|---:|---:|:--:|
| Persistent identifier | -0.122 | 0.2635 | 0.3953 | 1.0000 | no |
| Descriptive metadata | +0.122 | 0.2635 | 0.3953 | 1.0000 | no |
| Method declared | +0.018 | 0.8689 | 0.8689 | 1.0000 | no |
| Software licence | +0.244 | 0.0236 | 0.1418 | 0.1418 | no |
| Methodological transparency (R2) | +0.157 | 0.1488 | 0.3953 | 0.8929 | no |
| Data provenance (R3) | -0.067 | 0.5422 | 0.6506 | 1.0000 | no |
| _aggregate FAIR-R v1_ | +0.155 | 0.1535 | — | — | — |

### Outcome: `build_success`

| criterion | rho | raw p | BH-FDR q | Bonferroni p | survives FDR 0.05 |
|---|---:|---:|---:|---:|:--:|
| Persistent identifier | -0.114 | 0.2975 | 0.4274 | 1.0000 | no |
| Descriptive metadata | +0.114 | 0.2975 | 0.4274 | 1.0000 | no |
| Method declared | +0.007 | 0.9477 | 0.9477 | 1.0000 | no |
| Software licence | +0.209 | 0.0532 | 0.3190 | 0.3190 | no |
| Methodological transparency (R2) | +0.113 | 0.2995 | 0.4274 | 1.0000 | no |
| Data provenance (R3) | -0.101 | 0.3561 | 0.4274 | 1.0000 | no |
| _aggregate FAIR-R v1_ | +0.099 | 0.3644 | — | — | — |

## Q2b — Statistics hardening: Firth penalized logistic regression

The conference model fits 8 predictors on n=86 with ~48 events (~6 events per variable, below the conventional 10), and reports uncorrected p-values across 8 predictors x 2 outcomes. Firth's penalized likelihood removes the small-sample bias; p-values are penalized likelihood-ratio tests; correction is over all predictors within each outcome.


### Outcome: `resolve_success`  (events 48/86, 3 predictors, EPV=16.0)

| predictor (standardised) | Firth coef | odds ratio | penalized LR p | BH-FDR q |
|---|---:|---:|---:|---:|
| Software licence | +0.473 | 1.60 | 0.0057 | 0.0170 |
| Methodological transparency (R2) | +0.292 | 1.34 | 0.0341 | 0.0512 |
| Data provenance (R3) | -0.151 | 0.86 | 0.0668 | 0.0668 |

### Outcome: `build_success`  (events 45/86, 3 predictors, EPV=15.0)

| predictor (standardised) | Firth coef | odds ratio | penalized LR p | BH-FDR q |
|---|---:|---:|---:|---:|
| Software licence | +0.424 | 1.53 | 0.0095 | 0.0284 |
| Methodological transparency (R2) | +0.211 | 1.23 | 0.0500 | 0.0565 |
| Data provenance (R3) | -0.188 | 0.83 | 0.0565 | 0.0565 |

## Q3 — FAIR-R v2: does dropping the dead weight help?

v2 keeps only criteria that vary and re-weights them by their in-fold association with the outcome, rescaled to 100 points. Weights are derived **inside each training fold**, so the comparison is not circular. 10-fold stratified CV, 20 repeats.

| outcome | model | CV AUC (mean ± sd) |
|---|---|---:|
| `resolve_success` | FAIR-R v1 (aggregate) | 0.584 ± 0.188 |
| `resolve_success` | Software licence only | 0.595 ± 0.136 |
| `resolve_success` | FAIR-R v2 (re-weighted, in-fold) | 0.604 ± 0.186 |
| `build_success` | FAIR-R v1 (aggregate) | 0.555 ± 0.181 |
| `build_success` | Software licence only | 0.582 ± 0.132 |
| `build_success` | FAIR-R v2 (re-weighted, in-fold) | 0.574 ± 0.185 |

## Reading these results

1. **The instrument is mostly constant on this corpus.** 57.8 of 100 points (58%) are identical for all 96 repositories; only 6 criteria vary at all, and only three vary enough to enter a model. The aggregate score therefore cannot spread far (observed sd ~5.2), which is a property of the rubric meeting ML code repositories, not of the repositories being uniformly good.

2. **The null result is explained, not merely replicated.** Aggregate FAIR-R fails to predict reproduction because most of its budget is dead weight here. The dimension-level signal previously seen in *Reusable* is entirely the software-licence criterion: the other two Reusable criteria are invariant, and the criterion's rho equals the dimension's exactly.

3. **The licence effect is now robust — with a caveat to report honestly.** In the multivariable Firth model (3 usable criteria, EPV 15-16, well above the conventional 10) software licence survives BH-FDR correction for both outcomes (q=0.017 resolve, q=0.028 build). At the bivariate level it does not (q=0.14 across six criteria). The multivariable model has more power because it adjusts for R2 and R3; both numbers should appear in the paper rather than only the favourable one.

4. **Re-weighting does not rescue the instrument.** FAIR-R v2 reaches CV AUC ~0.60 versus ~0.58 for v1 — and a single bit, 'does the repository have a licence', reaches ~0.59 on its own. The differences are well inside one standard deviation. The honest claim is not 'our v2 is better' but 'no weighting of these criteria yields a useful predictor; the measurable signal reduces to one deterministic feature'.

5. **Implication for the extension.** This reframes the contribution from *we built a score* to *we show why FAIR-style scores do not transfer to executable research artifacts, and identify the small set of deterministic features that do carry signal*. That is a claim about the FAIR-assessment literature, not only about SRAF.
