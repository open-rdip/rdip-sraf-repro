# Restructured failure taxonomy (n=26 buildable repositories)

Regenerate with `python3 analysis/taxonomy_restructure.py`. The workshop paper's three families are separated here into findings, exclusions and measurement error, then re-expressed on two axes.

## 1. The three families are not the same kind of thing

| Locus | n | What it is |
|---|---:|---|
| `artifact` | 16 | Artifact failure (a finding) |
| `claim` | 5 | Excluded - claim not reproducible by construction |
| `scope` | 1 | Excluded - outside harness scope |
| `harness` | 4 | Measurement error - our harness |

- **Genuine artifact failures: 16.** Exclusions: 6. Measurement error: 4.
- The workshop paper reports **18 of 26** as documentation/artifact gaps. Once exclusions and our own harness bugs leave the denominator, the claim becomes **16 of 16** — every genuine artifact failure in the corpus is a documentation or artifact gap. Not compute, not fundamental difficulty.
- Two studies move out of the paper's family 1 on judgement (see §4); that is why this is 16, not 18.

## 2. Two-axis taxonomy

Axis 1 is *whose problem it is*; axis 2 is *who can fix it* — the three-way remedy split the workshop discussion already makes. Crossing them turns a flat list into guidance about where effort should go.

| Failure mode | n | Locus | Primary remedy | Also addressable by |
|---|---:|---|---|---|
| Placeholder command | 7 | `artifact` | `author-fix` | `extraction-research` |
| No run command | 4 | `artifact` | `author-fix` | `extraction-research` |
| Repository does not match paper | 3 | `artifact` | `author-fix` | — |
| Dead download (link rot) | 1 | `artifact` | `author-fix` | — |
| Gated dataset | 1 | `artifact` | `author-fix` | — |
| Hardware-bound metric | 2 | `claim` | `intrinsic` | — |
| Needs external device or service | 1 | `claim` | `intrinsic` | — |
| No numeric claim to test | 1 | `claim` | `intrinsic` | — |
| Production/online metric | 1 | `claim` | `intrinsic` | — |
| Dependency absent from our harness | 4 | `harness` | `harness-fix` | — |
| Out of scale for the harness | 1 | `scope` | `intrinsic` | — |

| | author-fix | extraction-research | harness-fix | intrinsic |
|---|---:|---:|---:|---:|
| `artifact` | 16 | 0 | 0 | 0 |
| `claim` | 0 | 0 | 0 | 5 |
| `scope` | 0 | 0 | 0 | 1 |
| `harness` | 0 | 0 | 4 | 0 |

## 3. Which FAIR-R criterion would have caught each artifact failure?

This is the bridge from the taxonomy to the instrument redesign: if the rubric already scored the thing that broke, a good score should have predicted success. It mostly doesn't — the modes map onto criteria that are either absent from the rubric entirely or among the ones that never vary.

| Failure mode | n | Covered by FAIR-R? |
|---|---:|---|
| Placeholder command | 7 | NOT COVERED - no criterion asks whether the run command is concrete |
| No run command | 4 | Reproducible R2 (methodological transparency) - partial coverage only |
| Repository does not match paper | 3 | Interoperable / Related links - INVARIANT (absent for all 96) |
| Dead download (link rot) | 1 | NOT COVERED - no criterion tests link liveness |
| Gated dataset | 1 | Accessible / Access level - INVARIANT (absent for all 96) |

**Read this with the variance audit.** The criteria these failures map onto are either *not in the rubric at all* (concrete run command, link liveness) or are among the 57.8 points that are invariant across all 96 repositories (Related links, Access level). So the instrument could not have predicted these failures even in principle. That is the mechanism behind the null result, and it is the argument for a code-native criterion set rather than a re-weighting.

## 4. Judgement calls for the inter-rater study

These two reassignments change the headline denominator and should be adjudicated by the second coder rather than asserted:

- **study001 — Out of scale for the harness.** Workshop paper filed this under documentation/artifact gaps. Moved: a 176B model is outside the harness's declared operating envelope, which is the definition of an exclusion.
- **study015 — No numeric claim to test.** Workshop paper filed this under documentation/artifact gaps. Moved: with no claimed number there is no reproduction to test, so it is an exclusion, not a failure.

Everything else follows mechanically from the recorded reason string.

## 5. Per-study assignment

| Study | Recorded reason | Mode | Locus | Remedy |
|---|---|---|---|---|
| study001 | `SKIP out-of-scale: PPL on BLOOM-176B / OPT-66B, beyond 1x4` | Out of scale for the harness | `scope` | `intrinsic` |
| study002 | `recipe had no run command` | No run command | `artifact` | `author-fix` |
| study003 | `placeholder_recipe` | Placeholder command | `artifact` | `author-fix` |
| study004 | `SKIP repo<->paper mismatch: repo is an IRC URL-title bot` | Repository does not match paper | `artifact` | `author-fix` |
| study005 | `SKIP no claimed number and repo<->paper mismatch (eDiff-I ` | Repository does not match paper | `artifact` | `author-fix` |
| study006 | `missing_system_dep:mujoco` | Dependency absent from our harness | `harness` | `harness-fix` |
| study007 | `recipe had no run command` | No run command | `artifact` | `author-fix` |
| study008 | `placeholder_recipe` | Placeholder command | `artifact` | `author-fix` |
| study009 | `dead_download:404` | Dead download (link rot) | `artifact` | `author-fix` |
| study010 | `recipe had no run command` | No run command | `artifact` | `author-fix` |
| study011 | `recipe had no run command` | No run command | `artifact` | `author-fix` |
| study012 | `placeholder_recipe` | Placeholder command | `artifact` | `author-fix` |
| study013 | `SKIP repo<->paper mismatch: repo is the Zenodo platform, n` | Repository does not match paper | `artifact` | `author-fix` |
| study014 | `missing_dependency:torch` | Dependency absent from our harness | `harness` | `harness-fix` |
| study015 | `SKIP no numeric claim captured` | No numeric claim to test | `claim` | `intrinsic` |
| study016 | `SKIP hardware-bound metric: steps per second (throughput)` | Hardware-bound metric | `claim` | `intrinsic` |
| study017 | `SKIP hardware-bound metric: processing time (seconds)` | Hardware-bound metric | `claim` | `intrinsic` |
| study018 | `placeholder_recipe` | Placeholder command | `artifact` | `author-fix` |
| study019 | `placeholder_recipe` | Placeholder command | `artifact` | `author-fix` |
| study020 | `missing_file_or_data` | Gated dataset | `artifact` | `author-fix` |
| study021 | `missing_dependency:torch` | Dependency absent from our harness | `harness` | `harness-fix` |
| study022 | `SKIP production A/B metric (Pinterest online gains), not r` | Production/online metric | `claim` | `intrinsic` |
| study023 | `SKIP needs mobile device/emulator + external VLM API` | Needs external device or service | `claim` | `intrinsic` |
| study024 | `missing_dependency:pip` | Dependency absent from our harness | `harness` | `harness-fix` |
| study025 | `placeholder_recipe` | Placeholder command | `artifact` | `author-fix` |
| study026 | `placeholder_recipe` | Placeholder command | `artifact` | `author-fix` |
