# RQ3 ground truth — layout, schema, and scoring

## Layout

    data/ground_truth/
      gold/   <study>/gold_standard.json          # 12 studies, thoroughly verified (headline)
      silver/ <study>/gold_standard.json          # 95 studies, quick-verified (scale)
              <study>/prompt.txt                   # the Gemini prompt used
              <study>/repo_metadata.json           # auto-parsed repo facts (deps/seeds/env/license)
      silver/README.md                             # entity statistics

Each `gold_standard.json` is a full **RDIP knowledge graph** for the paper:
`project`, `entities` (SoftwareApplication, Dataset, Method, Person,
Organization, Parameter, RandomSeed, ComputingEnvironment, EvaluationResult,
Activity), `relations`, and verification metadata (`_status`, `_verified_by`,
`_verification_depth`). Built with Gemini 2.5 Flash from *paper PDF +
`repo_metadata.json`*, then human-verified.

## Scope of RQ3 (reproducibility fields only)

SRAF's instrument uses reproducibility metadata, so the evaluator scores the
**seven reproducibility fields** and maps everything else away. The adapter
(`eval_extraction.py`) reduces both the ground truth and the model output to a
common shape:

| field (compared) | ground-truth entity | model output (`metadata`) |
|---|---|---|
| software | `SoftwareApplication` (name, version) | `dependencies` (name, version) |
| datasets | `Dataset` (name) | `datasets` (name) |
| methods | `Method` (name) | `methods` (name) |
| parameters | `Parameter` (name, value) | `hyperparameters` (name, value) |
| random_seeds | `RandomSeed` (value) | `random_seeds` (int) |
| environment | `ComputingEnvironment` (gpu, cuda) | `hardware` (gpu_model, cuda_version) |
| evaluation_results | `EvaluationResult` (metric, value, split) | `evaluation_results` (metric, value, split) |

`Person`, `Organization`, `Activity`, and `relations` are **out of RQ3 scope**
(they show RDIP's full expressiveness but aren't part of the reproducibility
instrument). Nullish gold phrasings like `"exact version not specified"` are
treated as absent.

## Scoring

- **lenient** — item found by its identifying key (software/dataset/method/param
  NAME; seed VALUE; eval (metric, split)).
- **strict** — key **plus** value (software name+version; param name+value; eval
  metric+value+split). Values canonicalised so `0.94`/`0.940`/`94%` match.
- Reported per field and overall as micro P/R/F1 (pool tp/fp/fn across studies)
  plus macro F1 (mean per-study F1).

## Note on fairness (paper-only extraction)

The model output is extracted from the **paper PDF only**; the ground truth also
drew on `repo_metadata.json`. SRAF supplies repo-derived facts (software
versions, code seeds, license, Docker env) **deterministically in Phase I**, so
RQ3 deliberately measures only the LLM's *paper*-extraction component. Lower
recall on repo-only software/seeds is expected and motivates SRAF's
deterministic+LLM fusion design — report per field so this is transparent.

## Run

    # headline (12 gold), per model, lenient then strict
    python evaluation/eval_extraction.py --model <slug> --tier gold
    python evaluation/eval_extraction.py --model <slug> --tier gold --strict
    # scale (95 silver)
    python evaluation/eval_extraction.py --model <slug> --tier silver

    # side-by-side across all models in one table
    python evaluation/compare_models.py --tier gold
