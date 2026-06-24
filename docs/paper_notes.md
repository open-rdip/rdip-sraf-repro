# SWJ Paper — Decisions & Findings Log

Running record of methodological decisions and empirical observations from the
build-out, to seed the Semantic Web Journal paper once experiments finish.
(Sessions: 2026-06-09, 2026-06-10.)

## Methodological decisions (affect Methods / Limitations sections)

- **Reproducibility is measured as environment reconstruction, not CI.** The
  AIT Slurm compute nodes have no Docker/Apptainer, so each declared environment
  is rebuilt in an isolated venv on the cluster. This is *stronger* framing than
  CI: it directly tests whether the declared metadata suffices to reconstruct the
  environment. Replace all "CI / continuous integration" language accordingly.

- **Two-level build outcome.** Each repo yields `resolve_success` (does the
  declared dependency set resolve into a consistent plan — `pip --dry-run`) and
  `build_success` (does it actually install, incl. compiled extensions). RQ1 can
  model resolution-failure vs build-failure as distinct outcomes — richer than a
  single pass/fail. `stage_failed` records where it died.

- **Build against the repo's DECLARED Python version (confound control).** The
  first corpus run built every repo on Python 3.12, which inflated resolution
  failure: old pins have no 3.12 wheels and old sdists fail to build on 3.12
  (removed `imp`/`zipimporter`/`pkg_resources`). We now resolve each repo's
  declared Python (conda `python=`, Dockerfile, `.python-version`, `runtime.txt`,
  `python_requires`) and build on a matching interpreter from a ladder
  (`~/pys/py38…py312`), defaulting undeclared repos to 3.10; we also add the
  PyTorch wheel index so `torch==x+cuYYY` pins resolve. This makes a
  resolution/build failure attributable to the repo, not our setup — a key
  validity move for RQ1. Keep the Python-3.12 baseline as a before/after
  comparison (`validation/results_py312baseline`).

- **`final_tier` is a stratifier, NOT the outcome.** It is computed purely from
  metadata presence (Dockerfile +3, environment.yml +2, requirements +1,
  setup.py +1, seed +2, stars>100 +1; tier=full if score>=5). Using it as the
  reproducibility outcome would make RQ1 circular. It only routes effort:
  build-test all, run-test the `full` tier. **Actual counts: 26 full / 70
  build_only** (proposal said 30/66 — corrected).

- **`imageDigest` = author-declared pin, measured statically.** We parse the
  digest only when the Dockerfile pins `FROM image@sha256:…`. We do NOT resolve
  digests ourselves (that would credit a pin the author never declared and
  answer the wrong question). Absence = a true negative reflecting that the
  researcher did not pin. Expect a low pin rate — itself a reportable finding
  and support for "Reproducible is the hardest dimension."

- **Run-test (execution / result reproducibility)** needs the GPU node and is
  scoped to the 26 `full`-tier repos; environment reconstruction (resolve+build)
  is the all-96 outcome. Execution-level reproducibility on CPU is out of scope
  (would produce spurious GPU-absence failures) — stated as a limitation.

## Empirical observations (candidate findings)

- **Artifacts are buried, not at the root.** Real repos place env specs in
  subdirs: transformers' Dockerfiles live under `docker/*/` (depth 2);
  DeepSpeed's under `docker/`; nanoGPT and DINO have *no* env files at all. A
  root-only scan misses most — the harness does a recursive, priority-ranked
  search (root > subdir > deeper; canonical filename > variant; non-aux > aux).

- **Canonical-filename selection matters.** First pass picked
  `requirements-1bit-mpi.txt` (one line: mpi4py) over the real
  `requirements/requirements.txt` — a false build pass. Fixed by preferring
  canonical names. Lesson worth a sentence: artifact *selection* is a
  non-trivial methodological step.

- **FAIR-R from env files alone is near-constant (~27.5/100).** Only identifier,
  software license, and commit hash fire (universal across Git repos). All
  discriminating variance lives in the LLM/PDF-extracted dimensions (seeds, eval
  results, methods, workflow language) + image digest. => The RAG path is on the
  critical path for RQ4; env-only scoring cannot answer it.

- **Build signal on CPU:** DeepSpeed's `requirements.txt` installs torch + full
  CUDA wheel stack cleanly on a CPU node (~45s) — pip pulls GPU-enabled wheels
  without a GPU present. So build-testing runs on `ASL-cpu`; only execution needs
  `ASL-gpu`.

- **First corpus run (Python-3.12 baseline, 97 repos) — interpret with care.**
  Resolution 37/86 (43%), build 35/86 (41%); 11 had no installable pip/setup
  artifact. Artifact placement: 72 root / 21 subdir / 3 deep / 1 none — i.e.
  ~25% keep specs outside the root. License detected 84%, commit 99%, FAIR-R flat
  17.5–27.5. BUT auditing the 49 resolution failures showed ~80% were the
  Python-3.12 confound (no 3.12 wheel / sdist build fails on removed stdlib),
  ~7 genuinely broken specs (nonexistent packages, malformed `requirements.txt`
  listing `json` or `Python>=3.7` as deps, pasted Python code), 2 a `setup.cfg`-
  only harness artifact (now fixed). The corrected version-aware re-run is the
  real RQ1 signal; the gap between the two runs quantifies environment rot.

- **Version-aware corpus (clean, 96/97 on the interpreter ladder) — the headline
  RQ1 result.** Controlling for declared Python: resolution 43% -> 55.8%
  (48/86), build 41% -> 52.3% (45/86); failures resolve=35, build-install=3,
  resolve-timeout=3. So ~half of declared ML environments still fail to
  reconstruct even on the correct interpreter. Declared a Python version: 42%;
  versions used 3.10=58 (default), 3.8=18, 3.9=7, 3.12=11, 3.11=2. RQ1 predictors
  (logreg, n=86): license presence significant for resolve (OR 7.3, p=0.026) and
  build (OR 7.7, p=0.024); has_conda borderline (p=0.05); log(triples) trending
  negative (p~0.05-0.07).

- **RQ4 interim result (graded re-score, env-only FAIR-R).** After applying the
  graded scorer, FAIR-R spreads 21.1-33.9 (mean 29.3) and **no longer
  significantly correlates with the outcome**: resolve rho=0.18 (p=0.09), build
  rho=0.15 (p=0.16). The earlier "significant" 0.25 was tautological (FAIR-R was
  essentially `license_present`, which predicts the outcome). Honest framing:
  with only environment-side metadata populated, metadata completeness does NOT
  predict reconstructability — a clean interim null that motivates the extraction
  phase. Nuance to test later: environment-spec completeness tracks project
  complexity (harder to build), so it may pull against the licence signal; this
  is what RQ4's empirical weight-refinement is meant to surface. Re-test RQ4 once
  the paper-extracted dimensions (seeds, methods, eval) populate the score.

- **Failure-mode taxonomy is itself a finding.** The resolution-failure causes
  (no wheel for declared interpreter, sdist build failure, conflicting pins,
  malformed/nonexistent requirements) are a reportable characterisation of *how*
  ML environments become unreconstructable.

## Infrastructure constraints (affect reproducibility-of-our-study statement)

- Storage approved: **200 GB** (not 300). Drove the streaming design: clone to
  node-local scratch -> process -> delete; only triples + results persist.
- Cluster policy: **max 1 running job, 1 node/job, 7-day max.** Corpus runs as a
  single sequential, resumable job (not a Slurm array).
- Containerless runtime: conda env (`~/envs/sraf`, call its python by abs path)
  + standalone Oxigraph binary (`~/bin/oxigraph` 0.5.8). No Apptainer on the CPU
  compute node (skynetcpu).
- **GPU node (ASL-gpu / skynet):** 2x RTX A6000 48 GB, **driver 560.35.03 =
  CUDA 12.6 max**. Apptainer IS present here, BUT the `vllm/vllm-openai:latest`
  container ships PyTorch built for CUDA 12.8 -> `torch._C._cuda_init()` fails
  ("driver too old, found 12060"). The driver can't be changed, so we DON'T use
  the container. Instead serve via **pip-installed vLLM pinned to a CUDA<=12.6
  build** in `~/envs/vllm` (`vllm==0.8.5`, torch 2.6+cu124), run directly on the
  GPU node — no container. `cluster/extract_corpus.sbatch` uses `$HOME/envs/vllm/
  bin/python -m vllm.entrypoints.openai.api_server`. 48 GB holds any 8-bit model
  on one card; OpenAI-compatible API on localhost; models from `HF_HOME`.

## What is built (code state)

- `build_harness/`: `artifact_finder.py` (recursive/ranked), `build_tester.py`
  (two-level resolve+build, declared-Python + PyTorch index), `python_version.py`
  (declared-version resolver + interpreter ladder), `repo_metadata.py`
  (identifier/license/commit), `process_repo.py` (orchestrator),
  `run_corpus.sbatch` (single-job, resumable), `merge_results.py` (re-import).
- `lifter/parsers/docker_parser.py`: extracts author-declared `@sha256` digest.
- `lifter/mapper/rdip_mapper.py`: `map_repo_metadata()`.
- `cluster/`: onboarding scripts (containerless), `download_models.sbatch`.
- `rag_pipeline/extractor.py`: refactored into a backend abstraction —
  `Extractor` ABC + `OpenAICompatExtractor` (covers openai / vllm / llamacpp via
  one OpenAI-compatible impl) + `GeminiExtractor`; `get_extractor(backend, model)`
  factory from config; lazy SDK clients; duplicate `_extract_google` bug removed.
  `extract_metadata` / `merge_extractions` kept stable for the pipeline.
  Multi-model = `get_extractor("vllm", model=<repo>)`. Tests in test_extractor.py.
  Extracts seeds, hyperparameters, methods, datasets, AND **evaluation results**
  ({metric,value,split} -> rdip:EvaluationResult via rdip:generatesResult) —
  the latter gives R3 its eval half AND the claimed-number ground truth for the
  run-test (RQ2). Code reconciled with ontology v2.0.0: datasets are dcat:Dataset
  (imported), not rdip:Dataset; scorer uses real v2.0.0 property names. Mapper
  tests in test_mapper.py.
- `rag_pipeline/run_corpus_extraction.py` + `cluster/extract_corpus.sbatch`:
  Phase II extraction over the corpus. ONE job (1-job policy) runs vLLM (in the
  vllm/vllm-openai Apptainer container, GPU) + Oxigraph + the extraction loop;
  conda-env python hits the vLLM OpenAI API over localhost. Run per model via
  `--export MODEL=<repo>`; resumable (marker files). Enriches study graphs ->
  re-score -> RQ4 becomes a real test. Models: Qwen2.5-14B-GPTQ-Int8 (verified),
  RedHatAI Llama-3.1-8B w8a8 (verified), Mistral-Small w8a8 (verify exact id).
  NOTE: multi-model RQ3 eval needs per-model JSON outputs (task #19, separate
  runner) — appending all 3 to one graph would mix them.
- `analysis/summarize_results.py`: corpus stats → `results_summary.md/.csv`.
- `analysis/predictor_analysis.py`: **Phase IV (RQ1/RQ4).** Logistic regression
  of resolve/build outcome on metadata predictors (odds ratios + p-values, with
  a regularised fallback for separation), and Spearman of FAIR-R vs outcome.
  Predictors = artifact presence/placement, license, log(triples), plus
  `has_seed`/log(stars) merged from `repo_list.csv`. Needs scipy+statsmodels.
- `tests/` + `pytest.ini`: **48-test pytest suite** (artifact finder, version
  resolver, repo metadata, docker parser, build-tester branches, all four
  conflict queries, summarizer). Caught a real bug: `DEPRIORITIZE` used substring
  matching so `"doc"` hit `"docker"`, nullifying the docs/test de-prioritisation
  — now token-based. (Methods note: artifact *selection* is non-trivial and was
  unit-tested.)
- **RQ2 semantic diff — complete & tested.** Four-conflict taxonomy now
  functional: `construct_{version,digest,seed,hardware}_conflicts.sparql` +
  `diff_engine.py` + `conflict_report.py`. New hardware query (CUDA/GPU/OS).
  Fixed 3 pre-existing bugs that made the diff non-functional: seed+digest
  queries had hardcoded `study001/002` graph URIs; the version query's
  name-match `FILTER` sat inside the reproduction `GRAPH` block (out-of-scope
  variable → zero matches). Validated end-to-end with rdflib on synthetic graphs.

## Outstanding before analysis

- **Version-aware corpus re-run** (in progress as of 2026-06-10): build the
  interpreter ladder, then `SRAF_FORCE=1` re-run; compare to py312 baseline.
- Phase IV **analysis module** — logistic regression + Spearman of resolve/build/
  result outcomes vs metadata predictors (RQ1/RQ4). Highest-leverage next build;
  prototype on baseline, run on corrected corpus. (Likely needs statsmodels.)
- GPU-node capability check (`srun --partition=ASL-gpu …`) — decides vLLM serving
  and the run-test harness.
- Model download (#4) for the RAG path.
- RAG/LLM extraction wiring -> seeds/methods/eval-results -> FAIR-R variance (RQ3,
  RQ4).
- Run-test harness for the 26 full-tier repos (result reproducibility, 0.5% tol).
- End-to-end diff-engine run against Oxigraph (query logic already verified).
- Executable SHACL shapes for the FAIR-R dimensions (proposal promises SHACL;
  scorer currently uses SPARQL ASK).

## Advisor feedback — progress meeting (2026-06-10)

- **TOP PRIORITY (gating): design the scoring metric rigorously BEFORE more
  automation.** The FAIR-R weights (e.g. identifier = 7.5) are currently ad-hoc /
  self-invented. Professors: do a careful design + analysis, grounded in the
  literature, not made up. Concretely: (1) review what FAIR/reproducibility
  assessment standards already do — **F-UJI** (Devaraju & Huber 2022, Horizon
  2020 / FAIRsFAIR), RDA FAIR Data Maturity Model, and software-specific FAIR
  (FAIR4RS); (2) **calibrate against reference papers** — take a paper that
  *should* score ~perfect and one that should score low, and derive/justify the
  criteria + weights from them; (3) benchmark our rubric against existing tools
  and document what is reused vs. novel. This also fixes our own finding that
  FAIR-R is currently flat and RQ4 is carried by the license criterion alone.
  → DONE (grounding + proposed rubric): see `docs/fair_r_scoring_rubric.md`.
  Key basis: RDA priority (Essential/Important/Useful) for within-dimension
  weights; F-UJI hierarchy + graded maturity scoring (benchmark); FAIR4RS for
  software criteria; ML Reproducibility Checklist for the novel Reproducible
  dimension; weights then empirically refined via RQ4. Calibrate against
  reference (badged/repro-challenge) papers + benchmark vs F-UJI.
  → CODE DONE: `dashboard/fair_r_scorer.py` rebuilt to graded scoring
  (absent/partial/full = 0/0.5/1.0) with RDA-priority weights
  (essential/important/useful = 3/2/1), Reproducible via explicit sub-weights
  (R1 0.4, R2 0.3, R3 0.3), recommendations sorted essential-first. Each
  criterion carries its mapped standard. 6 unit tests in
  `tests/test_fair_r_scorer.py` (perfect repo = 100, priority splits exact).
  SHACL DONE: 6 dimension shape files in `sre_engine/shacl/` (findable,
  accessible, interoperable, reusable, methodological, provenance) — severity =
  priority (essential->Violation, important/useful->Warning), wired into the
  diff_engine SHACL stage; parse + pyshacl tests in `tests/test_shacl_shapes.py`.
  Still TODO: confirm exact RDA priority labels from the spec table; update the
  Streamlit dashboard to the graded view; run the (quiet) FAIR-R re-score.
- Look into a second EU/Horizon-2020 **code/software evaluation tool** the
  professor referenced (FAIR-for-software / code assessment) — find + cite.
- **Framing:** add a use-case / significance slide BEFORE the RQs, and tie the
  RQs to the research vision. The use case to lead with: an author, before
  submitting, uploads their paper + materials and gets a FAIR-R score plus
  concrete recommendations to make the work more reproducible.
- **New idea — citation-based reproducibility signal.** When paper A cites paper
  B and reports a comparison (e.g. a results table), distinguish two citation
  types: (a) A actually re-ran B's system, vs (b) A copied B's reported numbers.
  Citation context is evidence of whether a system is runnable / results match;
  distinguishing the two is itself valuable. Worth exploring as an extra signal.
- **Result-level reproducibility (the 30 full-run subset):** be explicit that we
  execute these and compare obtained results against the numbers *claimed in the
  paper's tables* ("does it reproduce the advertised score"). Make the 66
  build-only / 30 full-run split explicit in slides. (Professors: very hard but
  very valuable — worth showing even partially.)
- **Logistics:** strong encouragement to submit to a conference (~mid–late July,
  possibly ~24 July; an information-science / digital-library venue near TPDL).
  Proceedings via Springer LNAI; workshops/posters/challenges via CEUR. Share the
  presentation slides with the professors by email.

## 2026-06-18 — scoring finalised (#14/#15/#16 closed)

- **#14 RDA priorities confirmed against the spec.** Web-fetched the RDA FAIR
  Data Maturity Model spec (Zenodo 3909563) and verified the priority of every
  criterion: F1/F2/F3 Essential; A1-01M Important, A1-02M Essential, A1.1-01M
  Essential; I1/I2/I3 Important; R1.1 Essential, R1.2 Important, R1.3 Essential.
  First pass had **3 mismatches**, now corrected in `fair_r_scorer.py`: landing
  page (Important→Essential), related links (Useful→Important), community
  standard (Useful→Essential). Rubric doc + tests updated; SHACL shapes already
  in place. → the rubric's within-dimension weights are now defensibly
  *standards-traceable*, not invented (the professor's #1 ask).
- **#16 dashboard graded view.** `dashboard/app.py` FAIR-R page rewired from the
  old binary output (met / severity) to the graded scorer: radar now plots
  **percent per dimension** (comparable axes); each criterion shows its maturity
  **level** (absent/partial/full) + **RDA priority** dot + points/max + the
  standard it maps to; recommendations are **priority-sorted** (Essential first)
  and show **points recoverable** per fix.
- **#15 calibration harness built** (`calibration/`): `run_calibration.py`
  (construct-validity check — pairwise rank concordance + high–low separation +
  optional Spearman/Mann-Whitney), `reference_set.yaml` (10 internal corpus
  anchors banded by independent evidence: seed+req+container & high build score
  = high; no-seed/no-container/low-score build-only = low — `external` ACM /
  ReScience-badged section left as a template to populate), and
  `fuji_benchmark.md` (procedure to score the dataset-PID subset with F-UJI and
  compare F/A/I/R per-dimension; Reproducible has no F-UJI analogue, validated
  via RQ4). 10 unit tests on the pure metrics. **Run pending:** execute
  `python calibration/run_calibration.py` on the cluster where Oxigraph holds the
  lifted corpus to get the actual construct-validity number for the paper.
- Test suite now **81 passing** (71 + 10 calibration).

## 2026-06-18 — multi-model extraction pipeline (#18 closed)

- **Pipeline is now genuinely multi-model.** `pipeline.run()` takes
  `backend`/`model`, builds one extractor (reused client) for the study, and
  writes each model's output to a **model-scoped graph**
  `…/graph/<study>/ext/<model_slug>` — so several models can extract the same
  paper without overwriting one another. An explicit `target_graph` overrides
  this (that's how the *chosen* model's triples get merged into the canonical
  study graph later, in #19/#20). Each run also persists the raw merged
  extraction to `data/extractions/<study>__<slug>.json` (backend, model,
  timestamp, counts, full metadata) for the gold-standard comparison.
- **Corpus runner** (`run_corpus_extraction.py`) loops several models in one
  submission via `SRAF_MODELS="vllm:<repo>,google:gemini-1.5-pro"` (falls back
  to the single configured model), with a **per-(study, model)** resume marker.
  NB: vLLM serves one model per server, so on the cluster run one *submission*
  per vLLM model (markers keep them separate); `SRAF_MODELS` multiplexing is for
  API backends. The sbatch already threads `MODEL`→vLLM + `LLM_MODEL`, and the
  always-model-scoped graph means different model submissions no longer collide.
- **Import hygiene fixes (found while testing):** removed a stray, unused
  `from sympy import python` in `chunker.py` (it forced sympy as a dep for
  nothing); made `pypdf`, `sentence_transformers`, and `faiss` **lazy** imports
  so the RAG modules import (and unit-test) without the heavy stack installed.
- 7 new tests (`tests/test_pipeline.py`): model_slug, per-model graph scoping,
  model threading, JSON persistence, explicit-target override, SRAF_MODELS
  parsing. **Test suite now 88 passing.**
- **Blocked on:** `~/envs/sraf/bin/pip install openai` on the cluster (+ vLLM
  serving) before the corpus extraction can actually run — code is ready and the
  run is a single `sbatch --export=ALL,MODEL=<repo> cluster/extract_corpus.sbatch`.
- **Decision:** extraction model access = **local vLLM (open-weights)**, not an
  API — weights live in `$HOME/models`, served by the pinned vLLM (0.8.5/cu124,
  driver-compatible) on `127.0.0.1:8000`, called by the `openai` client. Keeps
  the reproducibility story "locally hosted, citable open weights." `openai`
  client now confirmed present in the `sraf` env (2.43.0) — blocker cleared.

## 2026-06-18 — RQ3 extraction evaluator built (#19 harness)

- **Precision/recall/F1 evaluator** (`evaluation/eval_extraction.py`): compares
  each model's `data/extractions/<study>__<slug>.json` against hand gold files,
  per field (dependencies, seeds, hyperparameters, datasets, methods,
  evaluation_results, hardware). Two strictnesses — **lenient** (item found by
  identifying key) and **strict** (key + value, with value canonicalisation so
  `0.94`/`0.940`/`94%` compare equal). Reports micro P/R/F1 per field + overall,
  plus macro F1 (mean per-study F1). Pairs only studies that have both gold and
  an extraction; skips the rest. 12 unit tests; suite now **100 passing**.
- **Gold schema + template** (`evaluation/gold_schema.md`,
  `gold_standard/study001.template.json`): gold mirrors the extraction
  `metadata` block so they're directly comparable; annotate from the **paper
  PDF** (not the repo) since this measures paper extraction. Eval-result values
  are the paper's *claimed* numbers — same targets RQ #20 (result repro) checks
  re-run numbers against.
- **Remaining for #19 (human):** annotate 12→50 gold files, then run
  `python evaluation/eval_extraction.py --model <slug> [--strict]`. Auto-gold is
  deliberately NOT generated — gold must be human-verified to be a valid
  reference.

## 2026-06-18 — first real extraction run (smoke test, 3 papers) ✅

- **Local-vLLM extraction works end-to-end on the cluster.** `extract-16211`:
  vLLM served Qwen2.5-14B-Instruct-GPTQ-Int8, Oxigraph up, study001–003 extracted
  → per-model graphs `…/graph/<study>/ext/qwen-…` + JSON artifacts written, 148 /
  102 / 279 triples appended. Counts looked sane (e.g. study003: 7 params, 17
  eval results, 5 datasets).
- **Bug caught from real output + fixed:** Qwen sometimes emits the literal
  string `"null"` (and `"N/A"`, `"none"`, …) instead of JSON null — study001
  hardware came back `{'gpu_model':'null', …}`. A truthy `"null"` string would
  become bogus triples and inflate RQ3 false positives. Added `_clean`/`_key`
  nullish normalisation throughout `merge_extractions` (hardware + every list
  field's name/value), with a regression test. Suite now **101 passing**. (The 3
  smoke-test JSONs predate the fix; a full/`SRAF_FORCE` run will overwrite them.)
- **Benign warnings (no action):** sraf-env torch "CUDA driver too old" — that
  env doesn't use the GPU, embeddings run on CPU; specter2 "mean pooling" notice
  is expected for that model.
- **Quality note for later:** `methods` extraction is over-liberal (22–38 per
  paper) — likely to show low methods precision in RQ3; revisit the prompt once
  gold exists to calibrate against.
- **Before the full run:** `git pull` on the cluster to get the `_clean` fix,
  then drop `SRAF_LIMIT` for all 96.

## 2026-06-18 — ground truth received + RQ3 scope decided

- **Ground truth delivered by Suhel** at `data/ground_truth/{gold,silver}/<study>/
  gold_standard.json`: a full **RDIP KG per paper** (10 entity types + relations +
  activities + project), Gemini-2.5-Flash-built from *paper + repo_metadata.json*,
  then human-verified. **gold = 12** (thorough, first-author verified) → headline;
  **silver = 95** (quick-verified) → scale. Schema consistent across all 107 files;
  0 UNCERTAIN remaining.
- **RQ3 scope decision (important):** evaluate the **reproducibility fields only**
  (software, datasets, methods, parameters, seeds, environment, eval results).
  Rationale: the contribution is the SRAF engine; FAIR-R consumes only these
  fields; Person/Org/Activity/relations show RDIP expressiveness but aren't part
  of the instrument. **No prompt change, no extraction re-run** — Qwen run stands,
  Llama/Mistral run as-is.
- **Fairness framing:** gold was built from paper + repo metadata; the vLLM
  extraction is **paper-only**. SRAF supplies repo-derived facts (software
  versions, code seeds, license, env) **deterministically in Phase I**, so RQ3
  measures the LLM's *paper*-extraction component specifically. Lower recall on
  repo-only software/seeds is expected and **motivates the deterministic+LLM
  fusion design** — report per field for transparency.
- **Evaluator reworked to the real schema** (`evaluation/eval_extraction.py`):
  adapter maps both RDIP gold entities and pipeline output → the 7 repro fields;
  lenient/strict; micro+macro P/R/F1; `--tier gold|silver`. Added
  `compare_models.py` (auto-discovers model slugs → one side-by-side F1 table).
  `gold_schema.md` rewritten to document layout + mapping. Verified against real
  gold (self-match F1 = 1.0; all 12 normalise cleanly). Suite **103 passing**.
- **To produce numbers (cluster, where extractions live):** after `git pull`,
  `python -m evaluation.compare_models --tier gold` (and `--strict`, `--tier silver`).

## 2026-06-18 — RQ3 first cut + evaluator overhaul

- **First run (3 models × gold-12, exact match) gave alarmingly low F1 (~0.10
  overall).** Diagnosis (from inspecting the gold), NOT model failure:
  1. **seeds = 0 on gold** — all 12 gold papers contain *zero* RandomSeed
     entries, so F1=0 is undefined → must be **N/A**, not reported as failure.
  2. **software is rigged** — gold averages ~8 (up to 23) software because it
     includes the whole `requirements.txt`; the paper-only LLM finds the 2–4 the
     paper names. Repo-derived field → Phase-I territory, not the LLM's job.
  3. **methods/eval killed by exact string match** — gold names are verbose with
     acronyms ("Round-to-nearest (RTN)", "Camouflage-Aware Feature Refinement
     (CAFR)", metrics like "Zero-shot FID-30K"); a model outputting "RTN"/"FID"
     scored 0. Matching artifact, not wrong extraction.
  Stable signal even so: ranking **Mistral-24B > Qwen-14B > Llama-8B**.
- **Evaluator overhauled** (`eval_extraction.py`, `compare_models.py`):
  - **Two match modes** — exact + **fuzzy** (normalised, acronym-aware via
    parentheticals/initials, token-Jaccard ≥0.5, substring containment). Report
    BOTH for a defensible range ("exact X → fuzzy Y").
  - **Field grouping** — HEADLINE = paper-derivable (methods, parameters,
    datasets, evaluation_results, environment); software + random_seeds shown
    separately as **[repo]** asymmetry; fields with no gold support → **N/A**.
  - `compare_models` prints exact + fuzzy tables with a model legend
    (qwen/llama/mistral). 103 tests pass.
- **Next:** re-run `python -m evaluation.compare_models --tier gold` (+`--strict`,
  `--tier silver`) after pull; read the fuzzy HEADLINE as the fair RQ3 number.

## 2026-06-18 — ground-truth verification

- Built `evaluation/verify_ground_truth.py`: grounds each GT entity against its
  source (paper-derived → PDF text via pdftotext; software/seeds → repo_metadata).
  **GT precision is high: 96.9% of entities grounded** (gold 97.9%, silver 96.3%).
- **Fixed (both tiers):** removed **12 invalid EvaluationResults** with
  non-numeric/null values ("exact value varies…", "human-like", "qualitative",
  "scales well", "good agreement", null); removed **study002 `Wikitext-2`**
  (a KGE paper — confirmed absent; it actually uses FB15K-237/KINSHIP/UMLS/
  WN18RR/YAGO).
- **Two important caveats:**
  1. Most remaining 91 flags are **false positives** — pdftotext garbles result
     TABLES (so numeric eval values read as "not found") and concatenated/hyphen
     names mis-tokenise (e.g. ChestX-ray14 IS present). Do NOT mass-delete.
  2. The harness measures GT **precision only, not recall**. study002 exposed a
     **recall gap** (gold had 2/5+ datasets). Recall gaps *also* penalise the
     models in RQ3 (their correct extractions count as FP vs an incomplete gold).
     → low RQ3 is **partly GT incompleteness, not only model over-extraction**
     (correcting my earlier over-confident claim).
- Report: `evaluation/gt_verification_report.md`.
- **Decision:** no 12→50 gold expansion. **gold-12 (audited) = RQ3 headline,
  silver-95 = scale.** Eval-value recall left as a documented limitation.

## 2026-06-18 — RQ #20 result-reproducibility scaffolding

- Goal: does a repo that *builds* reproduce the **numbers claimed in its paper**?
  Scope = **26 full-tier repos** (`final_tier==full`); claimed numbers come from
  the audited GT `EvaluationResult` (52 claims total).
- Built `result_repro/`: `generate_manifest.py` (→ `manifest.yaml`: 26 repos ×
  claimed numbers + blank run/obtained fields), `run_result.sbatch` (clone →
  venv on declared Python → run `run.command` → log), `compare_results.py`
  (classify reproduced / partial / mismatch / run_failed; 5% rel or 0.01 abs
  tol; fuzzy metric match acc↔accuracy, 94%↔0.94), `README.md` (workflow).
  6 unit tests; suite now **110 passing**.
- **Semi-manual by necessity:** each repo runs differently, so the per-repo
  `run.command` + dataset staging is filled by hand from each README; the harness
  handles clone/env/run/log + the claimed-vs-obtained comparison.
- Report the build→run→result funnel: resolve% → build% → run% → result-match%.
  Even a partial subset reproducing headline numbers is a strong finding (advisors).
