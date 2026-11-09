# N10 — Badged contrast group

**Status:** plumbing done, twenty papers to be selected.
**Written before any badged repository was run.** The predictions in §3 are the
point of this document; recording them afterwards would make the whole exercise
worthless.

## 1. What this answers

The corpus is 96 repositories drawn without regard to artifact quality, and
nothing in it reproduced (0 of 17 attempted). That result has one serious
alternative explanation a reviewer will reach for immediately:

> Zero of seventeen might mean your harness is broken.

The three positive controls answer this weakly — they are HuggingFace artifacts
with documented headline numbers, not papers put through the full pipeline. A
stratum of papers that an independent body has certified as reproducible, run
through the *identical* code path, answers it properly.

Three questions, in descending order of value:

1. **Does the pipeline work?** If badged papers build and reproduce, the harness
   is vindicated and 0/17 becomes a statement about the population rather than
   about our tooling. If badged papers *also* fail, that is a stronger and more
   uncomfortable finding: artifact certification does not survive independent
   execution by a third party months later.
2. **Does the instrument discriminate?** N1 showed FAIR-R does not predict
   reproduction *within* a low-quality corpus. A contrast group tests whether it
   separates populations at all — a different and weaker claim, but one we
   currently cannot make either way.
3. **Do conflicts track quality?** If badged repositories show fewer paper↔repo
   conflicts (N4), conflict count becomes a validated signal rather than a
   descriptive statistic, and N7's triage model gets the positive examples it
   needs to be worth anything.

## 2. Design

**Separate manifest, never merged.** `validation/repo_list_badged.csv`, study
ids `badged001`…`badged020`. Both sweeps now read `SRAF_REPO_LIST`, so the
badged stratum runs through identical code:

```bash
SRAF_REPO_LIST=validation/repo_list_badged.csv \
  python3 build_harness/run_repo_facts_corpus.py --all
SRAF_REPO_LIST=validation/repo_list_badged.csv \
  python3 build_harness/run_tier_b_corpus.py --all
```

Merging the strata into one CSV would silently change every published 96-study
number, and December would be spent working out which figures moved and why.

**Selection criteria**, fixed before searching:

- an independent body certified reproduction — ACM *Results Reproduced* (the
  strongest ACM badge; *Artifacts Available* certifies only that a URL exists and
  is NOT sufficient), or an ML Reproducibility Challenge report that reproduced
  the paper's claims;
- a public repository that still resolves;
- a retrievable paper PDF;
- matched to the main corpus on year and rough domain.

Record `badge_source`, `badge_level` and `badge_url` per row. The badge claim is
itself evidence and has to be checkable; "we believe these are reproducible" is
not a stratum definition.

**Matching matters.** Venues that run artifact evaluation skew systems-heavy and
recent. Unmatched, "badged" would partly encode "published somewhere with an AE
track", and any difference could be field rather than quality. Match on year and
domain, record what could not be matched, and report the residual imbalance.

**Scope: static plus build.** FAIR-R, Tier-B, repo facts, paper↔repo diff, and a
build attempt. Every one of those pipelines already exists and runs from the
manifest, so this is incremental rather than new machinery. Result-level
reproduction for the badged set only if November has room.

## 3. Predictions, recorded in advance

Badged repositories will:

1. score higher on FAIR-R aggregate;
2. carry more Tier-B evidence, most visibly `concrete_run_command`;
3. show fewer paper↔repo conflicts per decidable type;
4. build at a higher rate than 26/96.

On (4) the honest expectation is a *higher* rate, not a high one. Environment rot
is time-dependent and indifferent to badges: a container digest that was never
archived decays whether or not a committee approved the artifact.

**If any prediction fails, it is reported as a failed prediction.** The value of
writing them here is that a null or reversed result stays publishable instead of
becoming a quiet omission.

## 4. Interpretation limits, to be stated with any result

- **n = 20.** Descriptive comparison only. No significance testing on a sample
  this size; report counts and effect direction, with confidence intervals wide
  enough to be honest about them.
- **The badged set is not a random sample of reproducible papers.** It is a
  sample of papers whose authors chose to submit to artifact evaluation, at
  venues that offer it. Self-selection runs in the same direction as the
  predicted effect.
- **The comparison is not causal.** Badges do not cause reproducibility; both
  plausibly follow from author diligence.
- **This is a contrast group, not a replacement corpus.** All headline numbers
  stay on the 96. Generalising *from* the badged set would repeat exactly the
  error the paper accuses FAIR-R of — an instrument built for curated artifacts
  and applied to working code.

## 5. Sequence

1. Fill `validation/repo_list_badged.csv` with twenty rows (~half a day).
2. Repo-facts and Tier-B sweeps with `SRAF_REPO_LIST` set.
3. Extraction for the badged stratum (cluster, vLLM, same three models).
4. `paper_repo_diff` per model over the badged ids.
5. Build attempts.
6. Comparison table: badged vs main, per metric, with the predictions from §3
   marked as met or failed.
