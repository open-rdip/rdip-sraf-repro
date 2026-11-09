# N2 - Does FAIR-style saturation generalise beyond SRAF?

Same corpus, same Level-1 outcomes, different instruments. Regenerate with `python3 analysis/instrument_audit.py`.


## Instrument: `sraf`  (n=96 scored, 86 build-attempted)

| dimension | criterion | max | levels observed | mean | sd | varies | if invariant |
|---|---|---:|---|---:|---:|:--:|---|
| Findable | Persistent identifier | 5.00 | partialx95, fullx1 | 2.53 | 0.26 | yes |  |
| Findable | Descriptive metadata | 5.00 | fullx95, absentx1 | 4.95 | 0.51 | yes |  |
| Findable | Landing page | 5.00 | absentx96 | 0.00 | 0.00 | **no** | floor |
| Accessible | Access protocol | 5.62 | fullx96 | 5.62 | 0.00 | **no** | ceiling |
| Accessible | Data licence | 5.62 | absentx96 | 0.00 | 0.00 | **no** | floor |
| Accessible | Access level | 3.75 | absentx96 | 0.00 | 0.00 | **no** | floor |
| Interoperable | Method declared | 6.67 | fullx94, absentx2 | 6.53 | 0.96 | yes |  |
| Interoperable | Workflow language | 6.67 | absentx96 | 0.00 | 0.00 | **no** | floor |
| Interoperable | Related links | 6.67 | absentx96 | 0.00 | 0.00 | **no** | floor |
| Reusable | Software licence | 7.50 | fullx77, absentx15, partialx4 | 6.17 | 2.77 | yes |  |
| Reusable | Commit + versioning | 5.00 | fullx96 | 5.00 | 0.00 | **no** | ceiling |
| Reusable | Community standard | 7.50 | absentx96 | 0.00 | 0.00 | **no** | floor |
| Reproducible | Computational environment (R1) | 12.00 | partialx96 | 6.00 | 0.00 | **no** | mid |
| Reproducible | Methodological transparency (R2) | 9.00 | partialx84, fullx11, absentx1 | 4.97 | 1.53 | yes |  |
| Reproducible | Data provenance (R3) | 9.00 | fullx75, partialx13, absentx8 | 7.64 | 2.78 | yes |  |

- Criteria that vary at all: **6 of 15** (40.0% of criteria).
- Criteria with a minority class of at least 5, so usable in a model: **3** (Software licence, Methodological transparency (R2), Data provenance (R3)).
- Point budget invariant: **57.8 of 100 (57.8%)**.

### Bivariate association with Level-1 outcomes


`resolve_success` (events 48/86)

| criterion | rho | raw p | BH-FDR q | survives 0.05 |
|---|---:|---:|---:|:--:|
| Persistent identifier | -0.122 | 0.2635 | 0.3953 | no |
| Descriptive metadata | +0.122 | 0.2635 | 0.3953 | no |
| Method declared | +0.018 | 0.8689 | 0.8689 | no |
| Software licence | +0.244 | 0.0236 | 0.1418 | no |
| Methodological transparency (R2) | +0.157 | 0.1488 | 0.3953 | no |
| Data provenance (R3) | -0.067 | 0.5422 | 0.6506 | no |
| _aggregate (fair_r_v1)_ | +0.155 | 0.1535 | - | - |

`build_success` (events 45/86)

| criterion | rho | raw p | BH-FDR q | survives 0.05 |
|---|---:|---:|---:|:--:|
| Persistent identifier | -0.114 | 0.2975 | 0.4274 | no |
| Descriptive metadata | +0.114 | 0.2975 | 0.4274 | no |
| Method declared | +0.007 | 0.9477 | 0.9477 | no |
| Software licence | +0.209 | 0.0532 | 0.3190 | no |
| Methodological transparency (R2) | +0.113 | 0.2995 | 0.4274 | no |
| Data provenance (R3) | -0.101 | 0.3561 | 0.4274 | no |
| _aggregate (fair_r_v1)_ | +0.099 | 0.3644 | - | - |

### Firth penalized logistic regression


`resolve_success` (events 48/86, 3 predictors, EPV=16.0)

| predictor (standardised) | coef | odds ratio | penalized LR p | BH-FDR q |
|---|---:|---:|---:|---:|
| Software licence | +0.473 | 1.60 | 0.0057 | 0.0170 |
| Methodological transparency (R2) | +0.292 | 1.34 | 0.0341 | 0.0512 |
| Data provenance (R3) | -0.151 | 0.86 | 0.0668 | 0.0668 |

`build_success` (events 45/86, 3 predictors, EPV=15.0)

| predictor (standardised) | coef | odds ratio | penalized LR p | BH-FDR q |
|---|---:|---:|---:|---:|
| Software licence | +0.424 | 1.53 | 0.0095 | 0.0284 |
| Methodological transparency (R2) | +0.211 | 1.23 | 0.0500 | 0.0565 |
| Data provenance (R3) | -0.188 | 0.83 | 0.0565 | 0.0565 |

### Cross-validated discrimination (10-fold, 20 repeats)

| outcome | model | CV AUC (mean +/- sd) |
|---|---|---:|
| `resolve_success` | aggregate score | 0.584 +/- 0.188 |
| `resolve_success` | Software licence only | 0.595 +/- 0.136 |
| `resolve_success` | re-weighted, in-fold | 0.604 +/- 0.186 |
| `build_success` | aggregate score | 0.555 +/- 0.181 |
| `build_success` | Software licence only | 0.582 +/- 0.132 |
| `build_success` | re-weighted, in-fold | 0.574 +/- 0.185 |

## Instrument: `howfairis`  (n=4 scored, 4 build-attempted)

| dimension | criterion | max | levels observed | mean | sd | varies | if invariant |
|---|---|---:|---|---:|---:|:--:|---|
| fair-software.eu | Public repository | - | passx4 | 1.00 | 0.00 | **no** | structural |
| fair-software.eu | Software licence | - | passx4 | 1.00 | 0.00 | **no** | ceiling |
| fair-software.eu | Package registry | - | passx2, failx2 | 0.50 | 0.58 | yes |  |
| fair-software.eu | Citation metadata | - | failx3, passx1 | 0.25 | 0.50 | yes |  |
| fair-software.eu | Quality checklist | - | failx4 | 0.00 | 0.00 | **no** | floor |

- Criteria that vary at all: **2 of 5** (40.0% of criteria).
- Criteria with a minority class of at least 5, so usable in a model: **0** (none).
- Unweighted instrument, so there is no point budget to report. Compare the criterion proportion above.

### Bivariate association with Level-1 outcomes


`resolve_success`: no variance in this subset (4/4 succeeded), so no association is estimable. Widen the instrument's coverage before reading anything into it.


`build_success`: no variance in this subset (4/4 succeeded), so no association is estimable. Widen the instrument's coverage before reading anything into it.


### Firth penalized logistic regression

_No criterion has a minority class of at least 5; nothing is estimable._


### Cross-validated discrimination (10-fold, 20 repeats)

| outcome | model | CV AUC (mean +/- sd) |
|---|---|---:|
| `resolve_success` | not estimable | - |
| `build_success` | not estimable | - |

## Cross-instrument summary

| instrument | n | criteria | varying | usable | invariant criteria | invariant points |
|---|---:|---:|---:|---:|---:|---:|
| sraf | 96 | 15 | 6 | 3 | 60.0% | 57.8% |
| howfairis | 4 | 5 | 2 | 0 | 60.0% | n/a (unweighted) |

Read the last two columns together. The criterion proportion is the comparable figure; the point proportion exists only where the instrument defines a budget.

Before concluding that an instrument saturates, check the *if invariant* column in its own table above. Ceiling invariance across several instruments supports the N1 claim. Floor invariance usually means the instrument was never designed for executable research artifacts, which is a finding about scope rather than about the literature, and structural invariance is an artifact of how this corpus was sampled.
