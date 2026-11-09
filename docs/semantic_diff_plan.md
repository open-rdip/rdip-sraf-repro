# Semantic Diff (journal item 2 / NII RQ2) — implementation plan

**Status:** plan for review, 17 Sept 2026. No code written yet.
**Compute:** CPU only. The whole corpus is 26,004 triples / 1.5 MB of extractions;
a full sweep runs in under a minute on one core. No GPU anywhere in this plan.

---

## 0. What I found in the existing code (this changes the design)

Three things, and the second is the good news:

1. **The built engine solves a different problem.** `sre_engine/diff_engine.py`
   exposes `run_diff(original_study_id, reproduction_study_id)` — it compares two
   *separate studies*. Its four conflict types (dependency version, container
   digest, random seed, hardware) are all environment facts. Item 2 promises
   something else: paper-vs-repository inconsistency (dataset, hyperparameters,
   a claimed metric the code never computes). Also, the original-vs-reproduction
   scenario **has no data** — nothing in the corpus reproduced.

2. **Paper-derived and repo-derived facts are ALREADY in separate named graphs.**
   - repo-derived (lifter + parsers) -> `https://w3id.org/rdip/graph/<study>`
   - paper-derived (RAG extraction)  -> `https://w3id.org/rdip/graph/<study>/ext/<model-slug>`

   So a paper↔repo diff is a two-graph comparison between graphs that both exist,
   which is exactly the shape `run_diff` already implements. The machinery is
   reusable with a change of arguments, not a rewrite.

3. **`merge_winner.py` destroys that distinction.** It appends the winning
   model's extracted triples into the *canonical* graph, after which repo-derived
   and paper-derived triples are indistinguishable. `PROV` is imported and bound
   in `rdip_mapper.py` but never used — the provenance design was intended and
   left unfinished. **This is the concrete defect the provenance work fixes.**

**Consequence for sequencing:** the experiment can run on the pre-merge named
graphs *today*, and must not be blocked on the provenance backfill. Provenance is
built in parallel because the released tool should support within-graph auditing.

---

## 1. Part A — Provenance in the mapper

### A1. Model

Attach provenance to the entity nodes the mapper already mints (dependency,
dataset, hyperparameter, seed nodes), not by reifying every triple — reification
would roughly triple the graph and make the SHACL shapes unreadable.

For each minted node:

```turtle
<instance/dep-a1b2c3>
    a                   rdip:SoftwareDependency ;
    rdip:dependencyName "torch" ;
    prov:wasDerivedFrom <source/study012/repo/requirements.txt> ;
    rdip:factSource     "repository" .          # repository | paper

<source/study012/repo/requirements.txt>
    a                prov:Entity ;
    rdip:sourceKind  "repository" ;
    rdip:sourcePath  "requirements.txt" .

<source/study012/paper/qwen-qwen2-5-14b-instruct-gptq-int8>
    a                prov:Entity ;
    rdip:sourceKind  "paper" ;
    prov:wasAttributedTo <agent/qwen-qwen2-5-14b-instruct-gptq-int8> ;
    rdip:extractedAt "2026-06-18T02:38:38Z"^^xsd:dateTime .
```

`rdip:factSource` is a redundant convenience literal so SPARQL can filter on
source without a join; `prov:wasDerivedFrom` is the real, standards-aligned link.

### A2. Code changes

| File | Change |
|---|---|
| `lifter/mapper/rdip_mapper.py` | add `source_uri()` / `_add_provenance()`; thread a `source` argument through `map_docker`, `map_conda`, `map_pip`, `map_dmp`, `map_repo_metadata`, `_add_dependency`. Default `"repository"` so existing callers keep working. |
| `rag_pipeline/mapper.py` | same for `map_extraction` and `map_recipe`, with `sourceKind "paper"` and the model slug as the attributed agent. |
| `lifter/lifter.py` | pass the actual file path each parser consumed. |
| `sre_engine/shacl/provenance_shapes.ttl` | shape asserting every minted node carries `rdip:factSource`. |
| `tests/` | provenance present on every node type; merged graphs still distinguish sources. |

### A3. Backfill

- **Paper side: free.** `data/extractions/*.json` holds all 285 extraction
  payloads, so re-running `map_extraction` needs no clones.
- **Repo side: one CPU array job.** Requires re-cloning to re-parse; same shape
  and cost as the Tier-B sweep (~25 min at `%8`). Reuse
  `build_harness/tier_b_corpus.sbatch` as the template.
- Stamp graphs with a `rdip:mapperVersion` for the same reason Tier-B outputs
  carry `rules_version` — so a corpus can never silently mix mapper versions.

---

## 1.5 CORRECTION (17 Sept, after reading the parsers) — the repo side has no experimental facts

`lifter/parsers/{pip,conda,docker}_parser.py` return **only environment facts**:
dependencies, python version, image digest, cuda version, os/arch.
`build_harness/` adds licence, commit, artefact paths. Nothing anywhere parses
repository configs for **datasets, hyperparameters or computed metrics**
(`dmp_parser.py` handles Data Management Plans, not repo configs).

The paper side has all of them — an extraction's `metadata` carries
`datasets [{name, version}]`, `hyperparameters [{name, value}]`,
`evaluation_results [{metric, value, split}]`, `methods`, `random_seeds`,
`hardware`, `dependencies`.

**So three of the five planned conflict types have nothing to compare against.**
`dataset_mismatch`, `hyperparameter_mismatch` and `metric_never_computed` each
need a repo-side fact that does not currently exist. Only
`dependency_version_mismatch` and (partially) `seed_mismatch` are computable
with what is stored today.

### Consequence: a repo-side experimental-fact extractor comes first

This is new work not in the original estimate, and it is now the critical path.
It is also, on reflection, **a larger contribution than the diff itself**: SRAF
currently describes a repository's *environment* deterministically and its
*experiment* only through an LLM with entity-level F1≈0.27. Extracting datasets,
hyperparameters and metric names deterministically from configs and code closes
that asymmetry, and the diff then becomes the evaluation of it.

Scope (deterministic, no LLM, same discipline as the Tier-B checks):

| Fact | Where it lives in a repo | Method |
|---|---|---|
| datasets | config yaml/py/json, dataloader calls, `torchvision.datasets.X`, dataset dir names | keyword + import + config-key extraction against an alias table |
| hyperparameters | config files, argparse defaults, `--lr`/`--batch-size` in documented commands | parse configs; read argparse defaults |
| metrics computed | metric names in configs (`--eval bbox`), logged format strings, imported metric libs | keyword scan over configs + eval scripts |
| seeds | `seed=`, `manual_seed(`, `--seed` | regex, already partly covered by `has_seed` |

Reuse `build_harness/tier_b_corpus.sbatch` for the sweep — it already clones,
checks, and deletes under the storage budget. Add ~4-5 days to Part B.

---

## 2. Part B — Retarget the diff engine

Keep `run_diff(original, reproduction)`; it stays valid if reproduction graphs
ever exist. Add:

```python
run_paper_repo_diff(study_id, model_slug)   # graph/<study>  vs  graph/<study>/ext/<slug>
```

### B1. Conflict types

| Type | Detects | Status |
|---|---|---|
| `dataset_mismatch` | paper names dataset X, repo config references Y | **new** |
| `hyperparameter_mismatch` | paper states lr/batch/epochs, repo config differs | **new** |
| `metric_never_computed` | paper claims metric M, no code path produces M | **new** |
| `dependency_version_mismatch` | paper/README states a version, requirements pins another | retarget existing |
| `seed_mismatch` | seed declared in paper vs set in code | retarget existing |

`digest` and `hardware` conflicts stay as-is for the original-vs-reproduction
path; they are not paper↔repo constructs.

### B2. Alignment (Stage 1)

Deterministic normalisation only — **no LLM**. Case-folding, punctuation and
whitespace stripping, a curated alias table for the common ML dataset and metric
names (`CIFAR-100` ≡ `cifar100`; `mAP` ≡ `mean average precision`).

This is a deliberate design constraint, not a shortcut. The contribution's value
is that it yields *real* precision and recall against ground truth. Putting a
language model in the alignment step reintroduces the extraction-quality
confound (F1≈0.27) that section N4 showed makes predictive claims untestable — a
reviewer could not tell whether a missed conflict was the detector's fault or the
matcher's. The alias table is auditable; a model is not.

---

## 3. Part C — Evaluation

### C1. Injected conflicts (primary, exact ground truth)

Take each clean study pair, inject known divergences one at a time, and measure
per-type precision and recall. Because we plant the conflicts, ground truth is
exact — this is what Tier-B could not have and is why this contribution can be
validated where the criterion set could not.

- 5 conflict types × ~3 severities × 96 studies, one injection per run.
- Report a per-type P/R table plus a confusion matrix across types
  (does a hyperparameter conflict get misreported as a dataset conflict?).

### C2. Real-conflict sample (secondary, realism check)

Injected conflicts test detection, not realism. Hand-verify a stratified sample
of ~20 studies for genuine paper↔repo divergence and report agreement with the
detector. Small, but it is the only evidence the detector fires on real
inconsistencies rather than only synthetic ones.

**State plainly:** C1 measures detection of conflicts we planted; C2 measures
whether real conflicts look like planted ones. Neither alone is sufficient.

### C3. Corpus sweep

Run over all 96 and report observed conflict rates by type — a descriptive
finding parallel to "27% document a concrete command".

---

## 4. Sequencing (nothing blocks on the backfill)

| Step | Depends on | Where | Est. |
|---|---|---|---|
| B: `run_paper_repo_diff` + 5 conflict types + alias table | nothing — pre-merge graphs exist | laptop | 4-5 d |
| C1: injection harness + per-type P/R | B | laptop | 3-4 d |
| A: provenance in mapper + shapes + tests | nothing | laptop | 2-3 d |
| A3: re-lift backfill | A | ASL-cpu array | 25 min |
| C2: real-conflict sample | B | human | 0.5 d |
| C3: corpus sweep + write-up | B, C1 | ASL-cpu | 1 d |

Roughly two to three weeks, entirely CPU.

---

## 5. Risks

1. **Extraction quality bounds the ceiling.** Paper-derived facts come from a
   pipeline with entity-level F1≈0.27. A "conflict" may be an extraction error,
   not a real inconsistency. Mitigation: report conflicts against the *extracted*
   claim (the workshop paper's existing convention), never assert that a specific
   paper contradicts its code, and re-run the diff on the item-3 frontier-model
   extractions to show how the rate moves with extraction quality. **That makes
   item 2 and item 3 mutually reinforcing** rather than independent.
2. **The alias table is hand-built**, so it is tuned on this corpus. Freeze it
   before the final sweep and report it in full, as with the Tier-B rule freeze.
3. **`metric_never_computed` is the hardest type** — proving absence of a code
   path is undecidable in general. Scope it to: no metric name appears in any
   documented evaluation command, config, or logged output string. Report it as a
   heuristic with an explicit false-positive rate, or drop it if C1 shows it is
   unreliable.
4. **Zero conflicts found** would be a null result. Unlikely given the corpus,
   but pre-commit to reporting it — a corpus with no detectable paper↔repo
   divergence is itself a finding about how little papers state precisely enough
   to contradict.
