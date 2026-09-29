# Tier-B results (n=96 repositories checked)

Regenerate with `python3 analysis/tier_b_analysis.py`. Checks defined in `build_harness/tier_b_checks.py`; swept by `build_harness/tier_b_corpus.sbatch`.

## Q1 — Do the Tier-B criteria vary?

| Criterion | absent | partial | full | sd (0/1/2) | varies usefully |
|---|---:|---:|---:|---:|:--:|
| concrete_run_command | 33 | 37 | 26 | 0.78 | yes |
| documented_entrypoint | 38 | 22 | 36 | 0.88 | yes |
| links_resolve | 0 | 30 | 66 | 0.46 | yes |
| data_obtainable_without_application | 2 | 0 | 94 | 0.29 | **near-constant** |
| repo_matches_paper | 6 | 16 | 74 | 0.58 | yes |

- **Four of five vary substantially.** Compare FAIR-R, where 9 of 15 criteria are identical for all 96 repositories and only 3 are usable.
- `data_obtainable_without_application` is the exception (94 full / 2 absent). It has the same saturation problem this paper criticises FAIR-R for, and should be reported as such rather than quietly kept: gated data is real but rare, so it cannot carry discrimination even though it caused a genuine failure.

**Standalone corpus finding:** only **26 of 96 (27%)** repositories document a concrete command that reproduces a reported metric. 37 document commands but none that reproduces a metric (or only placeholder ones), and 33 document no runnable command at all. This is measured deterministically from the documentation, with no language model involved.

## Q2 — Attribution: the author's gap, or the extractor's?

The workshop paper attributes **11 of the 16 artifact failures** to a command problem (7 placeholder + 4 no-command, plus any reclassified). Tier B asks, independently and deterministically, whether the repository documented a usable command anyway.

| Failure mode | docs: full | docs: partial | docs: absent |
|---|---:|---:|---:|
| placeholder recipe (n=7) | 3 | 2 | 2 |
| no run command (n=4) | 2 | 1 | 1 |

**5 of 11 command-related failures occurred in repositories that DO document a concrete evaluation command.** In those cases the artifact is not at fault: the extractor selected a placeholder command, or missed the documented one. On the taxonomy's remedy axis these move from `author-fix` to `extraction-research`.

| Study | Mode | concrete eval cmds in docs | placeholder eval cmds | evidence |
|---|---|---:|---:|---|
| study003 | placeholder recipe | 12 | 23 | `tracking_train_test.md: bash tools/slurm_test_tracking.sh \` |
| study010 | no run command | 16 | 4 | `quick_run.md: python tools/test.py configs/textdet/dbnet/dbnet_resnet1` |
| study011 | no run command | 31 | 1 | `README.md: python tools/test.py configs/arcface/resnet50-arcface_8xb32` |
| study012 | placeholder recipe | 4 | 0 | `README.md: sh tools/dist_test.sh \` |
| study019 | placeholder recipe | 5 | 2 | `GETTING_STARTED.md: python tools/test.py configs/faster_rcnn_r50_fpn_1` |

This makes quantitative what the workshop paper could previously only infer from a 3-artifact ablation (autonomous 0/3, gold recipes 2/3): extraction, not artifact quality, is the binding constraint for a measurable share of the corpus.

### Full cross-tabulation (26 buildable)

| Study | Failure mode | Recipe status | Docs grade |
|---|---|---|---|
| study023 | (excl) external device | `skipped` | `full` |
| study016 | (excl) hardware metric | `skipped` | `full` |
| study017 | (excl) hardware metric | `skipped` | `partial` |
| study015 | (excl) no claim | `skipped` | `absent` |
| study022 | (excl) online metric | `skipped` | `full` |
| study001 | (excl) out of scale | `skipped` | `partial` |
| study006 | (harness) missing dep | `run_failed` | `full` |
| study014 | (harness) missing dep | `run_failed` | `partial` |
| study021 | (harness) missing dep | `run_failed` | `partial` |
| study024 | (harness) missing dep | `run_failed` | `absent` |
| study009 | dead download | `run_failed` | `full` |
| study020 | gated dataset | `run_failed` | `absent` |
| study002 | no run command | `run_failed` | `partial` |
| study007 | no run command | `run_failed` | `absent` |
| study010 | no run command | `run_failed` | `full` |
| study011 | no run command | `run_failed` | `full` |
| study003 | placeholder recipe | `run_failed` | `full` |
| study008 | placeholder recipe | `run_failed` | `partial` |
| study012 | placeholder recipe | `run_failed` | `full` |
| study018 | placeholder recipe | `run_failed` | `partial` |
| study019 | placeholder recipe | `run_failed` | `full` |
| study025 | placeholder recipe | `run_failed` | `absent` |
| study026 | placeholder recipe | `run_failed` | `absent` |
| study004 | repo != paper | `skipped` | `absent` |
| study005 | repo != paper | `skipped` | `partial` |
| study013 | repo != paper | `skipped` | `absent` |

## Q3 — Do Tier-B criteria predict Level-1 outcomes?

n=86 build-attempted. 10-fold CV, 20 repeats.

| Outcome | Instrument | CV AUC |
|---|---|---:|
| `resolve_success` | FAIR-R v1 (aggregate) | 0.584 ± 0.188 |
| `resolve_success` | Software licence alone | 0.586 ± 0.121 |
| `resolve_success` | Tier-B (5 checks) | 0.476 ± 0.210 |
| `resolve_success` | Tier-B + licence | 0.549 ± 0.217 |
| `build_success` | FAIR-R v1 (aggregate) | 0.555 ± 0.181 |
| `build_success` | Software licence alone | 0.577 ± 0.123 |
| `build_success` | Tier-B (5 checks) | 0.517 ± 0.184 |
| `build_success` | Tier-B + licence | 0.572 ± 0.205 |

Tier-B criteria were designed to explain *result-level* reproduction failure, not environment reconstruction, so Level-1 is the wrong outcome for them and a modest result here is expected rather than disappointing. No Level-2 outcome exists to test against — nothing in the corpus reproduced — which is itself the limitation to state plainly.
