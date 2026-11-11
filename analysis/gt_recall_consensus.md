# Ground-truth recall, estimated from cross-model consensus

Consensus threshold: an item counts as consensus-missing when at least 60% of the extractors available for that study produced it and the reference does not contain it.

## Calibration against verification depth

If the reference's gaps come from light verification, consensus-missing items should be rarer where verification was thorough. If the rate is flat, consensus is measuring shared model bias instead.

| depth | gold items | consensus-missing | missing per gold item | est. recall |
|---|---:|---:|---:|---:|
| `standard` | 1945 | 1077 | 0.55 | 64.4% |
| `thorough` | 294 | 168 | 0.57 | 63.6% |

## By field

| field | gold items | consensus-missing | est. recall | gold items no model proposed |
|---|---:|---:|---:|---:|
| `dependencies` | 1074 | 65 | 94.3% | 1053 |
| `datasets` | 272 | 159 | 63.1% | 142 |
| `hyperparameters` | 234 | 201 | 53.8% | 197 |
| `random_seeds` | 111 | 1 | 99.1% | 105 |
| `evaluation_results` | 170 | 49 | 77.6% | 169 |
| `environment` | 90 | 29 | 75.6% | 83 |
| `methods` | 288 | 741 | 28.0% | 181 |

## Overall

- reference items: **2239**
- consensus-missing candidates: **1245**
- implied reference recall: **64.3%**
- candidate list for adjudication: `analysis/gt_consensus_candidates.csv` (1245 rows, ranked by agreement)

Consensus is not truth. These are candidates for a human to adjudicate, and the calibration table above is what says how much weight they carry.
