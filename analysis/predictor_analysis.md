# Phase IV predictor analysis — 97 repos

### Logistic regression — outcome: resolve_success

- n=86, positive=48 (48/86)

| predictor | coef | odds ratio | p-value |
|---|---:|---:|---:|
| has_docker | +0.44 | 1.55 | 0.567 |
| has_conda | +1.71 | 5.53 | 0.050 |
| has_pip | -1.16 | 0.31 | 0.302 |
| in_subdir | -0.08 | 0.92 | 0.919 |
| license_present | +1.99 | 7.31 | 0.026 * |
| has_seed | +0.37 | 1.45 | 0.568 |
| log_stars | -0.04 | 0.96 | 0.719 |
| log_triples | -0.46 | 0.63 | 0.053 |

### Logistic regression — outcome: build_success

- n=86, positive=45 (45/86)

| predictor | coef | odds ratio | p-value |
|---|---:|---:|---:|
| has_docker | +0.23 | 1.26 | 0.760 |
| has_conda | +0.96 | 2.61 | 0.236 |
| has_pip | -1.54 | 0.21 | 0.162 |
| in_subdir | -0.04 | 0.97 | 0.963 |
| license_present | +2.05 | 7.74 | 0.024 * |
| has_seed | +0.10 | 1.10 | 0.874 |
| log_stars | -0.09 | 0.92 | 0.386 |
| log_triples | -0.42 | 0.66 | 0.070 |

### Spearman correlation — FAIR-R vs outcome (RQ4)

- resolve_success: rho=+0.155, p=0.154  (n=86)
- build_success: rho=+0.099, p=0.364  (n=86)
