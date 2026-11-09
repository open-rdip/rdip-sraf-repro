# SWJ Paper — Decisions & Findings Log

Running record of methodological decisions and empirical observations from the
build-out, to seed the Semantic Web Journal paper once experiments finish.
(Sessions: 2026-06-09, 2026-06-10.)

## Methodological decisions (affect Methods / Limitations sections)

- **Reproducibility is measured as environment reconstruction, not CI.** Each
  declared environment is rebuilt in an isolated venv on the cluster. This is
  *stronger* framing than CI: it directly tests whether the declared metadata
  suffices to reconstruct the environment. Replace all "CI / continuous
  integration" language accordingly.
  - **CORRECTED 2026-09-11.** The original rationale ("AIT Slurm compute nodes
    have no Docker/Apptainer") is **false**: `ASL-cpu` carries
    `/usr/bin/singularity`, singularity-ce 4.1.1. The containerless rebuild is a
    *deliberate methodological choice*, not a consequence of missing tooling —
    a container would supply the very environment we are testing the metadata's
    ability to reconstruct, masking the measurement. Lead with that argument in
    the journal; it holds regardless of what the cluster supports.
  - Do **not** generalise the vLLM container failure into "no containers". That
    failure is specific and real: `vllm/vllm-openai:latest` ships PyTorch built
    for CUDA 12.8 while the GPU node's driver 560.35.03 caps at 12.6. The
    CPU-side engine container is unaffected.

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
- ~~Cluster policy: max 1 running job, 1 node/job, 7-day max.~~ **CORRECTED
  2026-09-11 — this was never enforced by Slurm.** Verified directly:
  `AccountingStorageType=(null)` and `AccountingStorageEnforce=none`, so no
  association or QOS limits can exist; `MaxArraySize=1001`, `MaxJobCount=10000`;
  partition `ASL-cpu` reports `MaxTime=UNLIMITED`, `MaxNodes=UNLIMITED`.
  **Job arrays are available and there is no job-count or wall-time cap.**
  The single-sequential-job corpus design was therefore self-imposed, not required.
- The real constraint is *shape*, not policy: `ASL-cpu` is a **single node**
  (`skynetcpu`, 128 CPUs, ~123 GB usable RAM — note the advertised 512 GB is not
  what Slurm reports) with `OverSubscribe=NO`. Arrays run, but all tasks contend
  for that one node, and the lab shares it. Throttle concurrency
  (`--array=1-50%8`) rather than flooding the queue.
- `DefMemPerNode=UNLIMITED`: a job omitting `--mem` requests the whole node and
  will pend indefinitely behind other users. Always pass `--mem` and `--time`.
- Outbound HTTPS works from both the login node and compute nodes (verified:
  `api.openai.com` returns HTTP 401, i.e. reached and authenticated-rejected).
  API-backed extraction can therefore run on the cluster.
- Containerless runtime: conda env (`~/envs/sraf`, call its python by abs path)
  + standalone Oxigraph binary (`~/bin/oxigraph` 0.5.8). ~~No Apptainer on the CPU
  compute node (skynetcpu).~~ **CORRECTED 2026-09-11: singularity-ce 4.1.1 IS
  installed at `/usr/bin/singularity` on skynetcpu.** `containers/sraf-engine.def`
  can therefore be built and shipped — see the tool-release task.
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

### RQ3 FINAL numbers (corrected GT, 2026-06-18)
- **gold-12 fuzzy headline F1:** qwen 0.223 / llama 0.230 / **mistral 0.273**
  (lenient); strict 0.194 / 0.203 / **0.241**. exact (lenient) 0.131/0.108/0.151.
- **silver-95 fuzzy headline F1:** qwen 0.208 / llama 0.185 / **mistral 0.226**.
- Per-field (gold, fuzzy lenient): **datasets ≈0.55** (best), parameters ≈0.29,
  environment ≈0.46, methods ≈0.18, **evaluation_results ≈0.00** (hard floor —
  neither side reads result tables reliably). seeds N/A on gold.
- **Ranking stable: Mistral-24B > Qwen-14B ≈ Llama-8B** (size-ordered).
- Abstract number = **best F1 ≈ 0.27** (Mistral, entity-aware match). Filled in
  docs/abstract.md; title added (SRAF: An Ontology-Grounded KG Framework…).

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

---

# 2026-09-11 — Journal extension (New Generation Computing): findings to reuse

Everything below is computed from data in this repo and is regenerable. Scripts:
`analysis/criterion_validity.py`, `analysis/taxonomy_restructure.py`,
`analysis/code_native_criteria.py`. Outputs: the matching `.md` files in
`analysis/`. Numbers here are the ones to quote in the extension.

## A. The thesis (use this framing, not "we made FAIR-R predictive")

> Reproducibility scores measure how well a study is *described*, not whether it
> *reproduces*. We show this at two levels over 96 ML repositories, explain the
> failure mechanically — a FAIR-style rubric is largely invariant on executable
> artifacts — identify the small set of deterministic signals that do carry
> information, and turn that into a triage procedure for verification effort.

This is a claim about the FAIR-assessment literature, not only about SRAF. Both
prior papers become evidence for it. **Do not promise "FAIR-R made predictive"**
— §C shows re-weighting does not deliver that, and the title would oversell.

## B. Variance audit — the mechanism behind the null result ★ headline

Of FAIR-R's 100 points, **57.8 are identical for all 96 repositories** (9 of 15
criteria have zero variance): Landing page, Data licence, Access level, Workflow
language, Related links, Community standard (absent for all 96); Access protocol,
Commit + versioning (full for all 96); Computational environment R1 (partial for
all 96). Three more are near-constant (differ on 1–2 repos): Persistent
identifier, Descriptive metadata, Method declared.

**Only three criteria carry usable variation:** Software licence (7.5 pts),
Methodological transparency R2 (9.0), Data provenance R3 (9.0).

Consequences to state explicitly:
- The tight observed distribution (mean 49.41, sd 5.23) is a property of the
  rubric meeting code repositories, not of repositories being uniformly poor.
- The aggregate cannot predict because most of its budget is a constant.
- The dimension-level *Reusable* signal is **entirely** the licence criterion —
  its rho equals the dimension's exactly; the other two Reusable criteria are
  invariant.

## C. Statistics hardening (fixes the conference version's fragility)

The conference model fits 8 predictors on n=86 with ~48 events (~6 EPV, below
the conventional 10) and reports uncorrected p across 8 predictors × 2 outcomes.
Replacement: Firth penalized logistic regression, penalized likelihood-ratio
p-values, criteria entering only if their minority level is seen ≥5 times
(3 predictors, EPV 15–16), Benjamini-Hochberg within each outcome.

- **Software licence survives correction**: q=0.017 (resolve), q=0.028 (build).
- **Report the tension honestly.** Bivariate Spearman does *not* survive
  (q=0.14 across six criteria). The multivariable model has more power because
  it adjusts for R2 and R3. Give both numbers; do not quote only the favourable
  one.
- Near-constant predictors (differ on 1–2 repos) are mutually collinear and make
  penalized likelihood diverge — hence the ≥5 entry rule.

## D. Re-weighting does NOT rescue the instrument

Cross-validated AUC, 10-fold × 20 repeats, weights derived **inside** each
training fold (so not circular):

| Instrument | resolve | build |
|---|---:|---:|
| FAIR-R v1 (aggregate) | 0.584 | 0.555 |
| Software licence alone | 0.586–0.595 | 0.577 |
| FAIR-R v2 (re-weighted) | 0.604 | 0.574 |
| Code-native Tier A (scored) | 0.622 | 0.574 |

All within one sd of each other. **Claim: no weighting of these criteria yields
a useful predictor; a single deterministic bit does as well as the whole rubric.**

## E. Restructured failure taxonomy (supersedes the workshop's three families)

The workshop's three families are not the same kind of thing: family 1 is
findings, family 2 is an exclusion criterion (the paper says so itself), family 3
is measurement error in our harness. Reporting "18 of 26" divides findings by a
denominator containing exclusions and our own bugs.

Restructured over the 26 buildable repositories:

| Locus | n | What it is |
|---|---:|---|
| `artifact` | 16 | genuine failures — a finding |
| `claim` | 5 | excluded: metric not reproducible by construction |
| `scope` | 1 | excluded: outside the 1×48GB harness envelope |
| `harness` | 4 | measurement error (our missing deps) |

**New headline: 16 of 16 genuine artifact failures are documentation or artifact
gaps.** Placeholder command (7), no run command (4), repo≠paper (3), dead
download (1), gated dataset (1). Nothing attributable to compute.

Two reassignments out of the workshop's family 1, flagged for the second coder:
**study001** (176B model — outside harness scope, not a documentation gap) and
**study015** (no numeric claim — nothing to reproduce against). These move the
denominator from 18 to 16; do not assert them without adjudication.

Second axis = remedy class, which the workshop discussion already uses without
naming it: `author-fix` / `extraction-research` / `harness-fix` / `intrinsic`.
Crossing locus × remedy turns a flat list into guidance on where effort goes.

## F. The bridge — why the instrument could not have worked ★ strongest result

Mapping each artifact failure to the FAIR-R criterion that would have caught it:

| Failure mode | n | FAIR-R coverage |
|---|---:|---|
| Placeholder command | 7 | **not in the rubric at all** |
| No run command | 4 | Reproducible R2, partial only |
| Repo does not match paper | 3 | Related links — **invariant (absent for all 96)** |
| Dead download (link rot) | 1 | **not in the rubric at all** |
| Gated dataset | 1 | Access level — **invariant (absent for all 96)** |

**15 of 16 failures map onto criteria that are either absent from the rubric or
inside the invariant 57.8 points.** The null result is therefore *structural*,
derivable rather than merely observed. This is the argument for new criteria
rather than new weights, and it is the paper's strongest single move.

## G. Code-native criteria

**Tier A** (computable now, from stored artefacts; 9 criteria): licence present,
Python declared, docker / conda / pip present, >1 env declaration, artefacts at
root, artefact count, log triples. **9 of 9 vary** (vs 6 of 15 for FAIR-R).
AUC 0.622 / 0.574 (§D). Honest reading: better than FAIR-R on resolve, *not*
better than licence-alone on build, and **nothing survives FDR univariately**
(licence closest, q=0.128). Tier A is a finding — the signal is not in the
metadata anyone currently collects — but it is not the constructive contribution.

**Tier B** (the constructive contribution; NOT yet computable — each needs a new
static check in the build harness plus a corpus re-clone):

| Criterion | Check | Evidence |
|---|---|---|
| `concrete_run_command` | documented command with no unfilled placeholder | 7/16 failures |
| `documented_entrypoint` | any documented route to a reported number | 4/16 |
| `links_resolve` | declared checkpoint/dataset URLs return 200 | 1/16, grows with age |
| `data_obtainable_without_application` | data not gated behind an application | 1/16 |
| `repo_matches_paper` | linked repo corresponds to the paper | 3/16 |

15 of 16 observed failures map onto these five, and each is a cheap static test.
**This is the critical path for the December draft.**

## H. Corrections to published / recorded numbers

- **Corpus is 96, not 97.** `summarize_results.py` and `predictor_analysis.py`
  globbed `validation/results/*.json` indiscriminately and counted
  `study001_vs_study002.json` (a WS2 semantic-diff output) as a repository.
  Symptoms: "97 repos processed", "86/97", "license 81/97 (83.5%)", "commit hash
  96/97", "1/97 with no env files" — the last two were qualitatively wrong (the
  phantom row *was* the missing-commit, no-env-file repo). Fixed with a
  `^study\d{3}$` guard. **Headline percentages divide by 86 (build-attempted) and
  were never affected**, and `predictor_analysis.py` always read the raw JSONs,
  so no published coefficient changes.
- **FAIR-R distribution**: the checked-in `results_summary.csv` was stale (a
  broken narrow band ~26–34, all 96 "poor"). Correct values from the raw results:
  mean **49.41**, median 51.79, sd **5.23**, min 26.62, max 56.29; **61 fair /
  35 poor**. The SRAF paper reports mean 49.6, sd 5.1 — a ~0.2 drift, immaterial,
  but use the recomputed figures in the extension.
- **New result the checked-in `predictor_analysis.md` predated**: per-dimension
  Spearman. Reusable rho=+0.244 (p=0.024, resolve) / +0.209 (p=0.053, build);
  Findable, Interoperable, Reproducible flat. See §B for why.
- Workshop paper wording: it calls the cluster "containerless". ASL-cpu carries
  singularity-ce 4.1.1, so in the extension say **containerless *harness***, and
  justify it methodologically (a container supplies the environment whose
  reconstructability we are measuring), never by cluster capability.
- Two-phase pipeline: justify by **the ablation**, not GPU scarcity. Freezing the
  recipe between phases is what makes autonomous-vs-gold attribution possible
  (0/3 vs 2/3). ASL has 4×A6000, so "does not fit on one 48GB GPU" invites the
  question why two cards were not used.

## I. Threats to validity — applying the instrument to ourselves

Five defects found in our own released artifact during this session, all now
fixed. Worth a short paragraph: we turned the instrument on our own artifact and
found the same failure family we found everywhere else — documentation and
artifact gaps, `author-fix` remedy class.

1. `results_gold.json` / `results_silver.json` did not reproduce Table 5 (gave
   F1 0.133/0.108 vs the published 0.273/0.226). They were output from a
   pre-`--match` script version, i.e. the *exact*-match mode, with no `fuzzy` key
   recorded. The published table is correct and reproduces exactly with
   `--match both`. **Classifies as: placeholder/undocumented-configuration.**
2. Eleven stale `rdip-sre` paths in the runbook and sbatch files (repo renamed to
   `rdip-sraf-repro`). **repo≠paper-link family.**
3. `cluster/README.md` instructed users to set `--account` on a cluster with no
   accounting database — any account fails the job with `InvalidAccount`.
4. No container shipped, although the discussion recommends archived container
   digests to authors. Now built in CI and published to GHCR.
5. `result_repro/results/` was gitignored, so the per-study rows behind the
   taxonomy were **not** released — while the availability statement says they
   are. Now tracked (rows + summary.json; bulk logs still ignored).

## J. Open decisions

- Ask the SI editors whether one submission may extend **both** the main-track
  and workshop papers. Changes the structure; get it early.
- Corpus extension: use a **bounded held-out validation set (~40–50 repos)**, not
  a general expansion. A redesigned instrument fitted and evaluated on the same
  96 is circular, so held-out data is *required*, not optional. Also bounded by
  the 200 GB L-tier quota (900 THB/month; XL is 1,500).
- Instrument comparison (F-UJI / FAIRshake): pre-specify it as **variance and
  predictive validity**, never a score bake-off. A higher score is not "better" —
  that is the thesis. Every outcome is then publishable.
- Multi-model extraction contradicts the recorded decision "extraction access =
  local open weights, not an API". Resolve in text: open weights remain the
  reproducible production path; API models establish an upper bound for the
  ablation only.
- Second coder needed for the taxonomy inter-rater study (26 rows in
  `analysis/taxonomy_coding_sheet.csv`; only the 16 artifact cases need coding,
  on two axes → two kappa values).

## K. Tier-B checks built — and an unplanned result from validating them

`build_harness/tier_b_checks.py` (+ `run_tier_b_corpus.py`, `tier_b_corpus.sbatch`,
`tests/test_tier_b_checks.py`, 31 tests passing). Deterministic, evidence-bearing,
offline by default; graded 0/1/2 to match FAIR-R's `LEVEL_FACTOR`.

**Detector validation.** The placeholder detector reproduces the taxonomy's
placeholder/concrete split on all 13 recipes that carry a command: precision 1.00,
recall 1.00. Two regex bugs found and fixed in the process, both the same class —
`\b` does not match before an underscore, so `/path_to_maskrcnn_benchmark/` and
`eval_extraction.py` were silently missed. Also: a `$VAR` the same snippet assigns
(`export NGPUS=8 && ... $NGPUS`) is runnable and must not count as a placeholder.

**The unplanned result (worth a subsection of its own).** Running the checks on
real clones disagrees with the recipe labels — and the disagreement is signal,
not error:

| Study | Recipe label | Docs contain (concrete eval / placeholder eval) |
|---|---|---|
| study003 | placeholder | **30** / 23 |
| study012 | placeholder | **4** / 0 |
| study019 | placeholder | **6** / 3 |
| study024 | concrete | 0 / 0 |

The recipe classification measures *what the extractor produced*; Tier B measures
*what the artifact documents*. For study003/012/019 a concrete evaluation command
**was** documented and the extractor selected a placeholder one instead. For
study024 the repository documents no command at all, yet a recipe was produced —
so the extractor inferred it from the file tree rather than the documentation.

**Consequences for the paper:**

1. The "placeholder command" mode (7 of 16 artifact failures) is **not purely an
   author-side gap**. For at least three of the seven, the remedy class on axis 2
   is `extraction-research`, not `author-fix`. The restructured taxonomy must be
   re-scored with this evidence before the numbers are quoted.
2. This *strengthens* the workshop paper's own conclusion ("execution works;
   extraction is the bottleneck") and makes it quantitative rather than inferred
   from the 0/3 vs 2/3 ablation alone.
3. It gives a capability neither prior paper has: an independent, deterministic
   measurement of whether the artifact documented a usable command, which lets
   each failure be attributed to the author or to the extractor **per study**.
4. Do **not** tune the Tier-B checks to agree with the recipe labels. They are
   different constructs; forcing agreement would destroy the comparison.

**Next analysis (needs the corpus sweep):** cross-tabulate, over the 26 buildable
repositories, the recipe outcome against the Tier-B `concrete_run_command` grade.
The cell that matters is *recipe placeholder × docs concrete* = failures caused by
extraction, not by the artifact. That number is a headline candidate.

**Caveat to carry:** the checks were designed against this corpus's failure modes,
so their construct validity on held-out repositories is untested — another reason
the bounded held-out set in §J is required rather than optional.

## L. Storage budget — the declared plan was right about artifacts, wrong about tooling

Measured on the cluster 2026-09-11, against the 200 GB Student-ASL "L" quota
(900 THB/month, 6-month minimum; XL is 1,500):

| Consumer | Size | In the budget table? |
|---|---:|---|
| `~/models` (HF_HOME, 3 open-weight models) | 49 GB | yes — allocated 48 GB ✓ |
| `~/.cache/pip` | **44 GB** | **no** |
| `~/slm-code-gen-eval` (unrelated project) | 33 GB | n/a |
| `~/.apptainer/cache` (OCI blobs) | **25 GB** | **no** |
| `~/.cache/huggingface` (pre-HF_HOME duplicate) | **24 GB** | **no** |
| `~/envs` (conda + vllm) | 15 GB | yes — allocated 8 GB (under) |
| `~/.conda` | 7.1 GB | no |
| repo + triplestore + misc | ~2 GB | yes |

Total reached ~201 GB against a 200 GB quota, which is why
`singularity pull` failed mid-conversion with `disk quota exceeded` and left no
`.sif` behind.

**The finding worth stating:** the declared budget in `cluster/README.md`
accounted correctly for every *artifact* (models, corpus, triplestore, results)
and for none of the *tooling* caches. Those caches consumed 93 GB — nearly twice
the 53 GB safety margin — and did so silently, because nothing in the plan
attributed them to anyone. This is the same class of omission the corpus study
measures in other people's repositories: the declared environment description is
accurate about what the author thought about, and silent about what they did not.
Worth one honest sentence in the reproducibility-of-our-own-study statement.

**Fixes applied:** caches redirected off the home volume
(`PIP_CACHE_DIR`, `APPTAINER_CACHEDIR`, `APPTAINER_TMPDIR` -> `/tmp/$USER-*`),
`HF_HOME=$HOME/models` exported in `.bashrc` so jobs cannot re-download into
`~/.cache`, and the engine image slimmed to `requirements-engine.txt` (drops
sentence-transformers -> torch, ~3.2 GB -> est. 0.5-0.7 GB).

**Update the budget table in `cluster/README.md`** to carry an explicit tooling
line before releasing it; a storage plan that omits its own build caches is not a
plan others can follow.

## M. Tier-B tuning history, and the freeze (threats to validity)

The `concrete_run_command` check was tightened three times, each after real data
exposed a false positive. This history belongs in the paper, not just in git:

| Pass | Admitted as "concrete evaluation command" | Why wrong |
|---|---|---|
| 1 | any concrete command anywhere in the docs | a concrete `pip install` passed a repo whose eval command was `/path/to/ckpt` |
| 2 | `python -m pytest --lf`, `train_net.py` | a unit-test runner and a training run do not regenerate a reported metric |
| 3 | `demo/webcam.py --min-image-size 300` | a demo shows the model runs; it does not reproduce a benchmark number |

Final scope: `test|eval|evaluate|evaluation|reproduce|benchmark|validate`, minus
test runners, training commands and single-input demos. 45 regression tests.

**Reported counts moved materially between passes** — the "command-related
failures that occurred despite a documented working command" figure went from
7/11 (pass 1) downward as each false-positive family was removed. Any number
quoted from an earlier pass is wrong.

**The freeze, and why.** Further tuning is now prohibited, because the heuristic
is being iterated against the same 96 repositories whose statistics it will be
used to report — which is overfitting, however principled each individual change
looked. Two consequences for the paper:

1. **State the limitation plainly.** Distinguishing "a command that reproduces
   the paper's reported metric" from "a command containing the word test" is not
   reliably decidable statically. Three passes were needed and the third was
   still finding false positives. The automated grade is an *upper bound* on how
   many repositories document a usable evaluation command.
2. **Human adjudication is not optional here.** The second coder (§J) must
   adjudicate the `concrete_run_command` grade on the 26 buildable repositories
   specifically, not only the failure-mode labels. Report the automated grade and
   the adjudicated grade side by side, with agreement. If they diverge widely,
   the honest conclusion is that the criterion needs a human in the loop — which
   is itself a finding about the limits of deterministic auditing, and a fair
   counterweight to this paper's criticism of LLM-based extraction.
3. **The held-out corpus (§J) is now load-bearing**, not merely good practice:
   it is the only way to show the tuned heuristic generalises beyond the repos
   that shaped it.

## N. Tier-B frozen results (rules v4, all 96, single sweep) — numbers to quote

Verified single-version corpus: `rules_version` = 4 for all 96, statuses all `ok`.
Supersedes every Tier-B number quoted before 2026-09-17.

### N1. Variance — 4 of 5 criteria discriminate

| Criterion | absent | partial | full | sd |
|---|---:|---:|---:|---:|
| concrete_run_command | 33 | 37 | 26 | 0.78 |
| documented_entrypoint | 38 | 22 | 36 | 0.88 |
| links_resolve | 0 | 30 | 66 | 0.46 |
| data_obtainable_without_application | 2 | 0 | 94 | 0.29 |
| repo_matches_paper | 6 | 16 | 74 | 0.58 |

Against FAIR-R's 9-of-15 invariant criteria, this is the intended contrast.
**But report `data_obtainable_without_application` honestly**: at 94/2 it saturates
exactly as the criteria this paper criticises do. Gated data is real but rare, so
it cannot discriminate even though it caused a genuine failure. Keep it as an
audit flag; do not count it as a discriminating criterion.

### N2. ★ Headline, deterministic, n=96

> **Only 26 of 96 (27%) repositories document a concrete command that reproduces
> a reported metric.** 37 document commands but none that reproduces a metric
> (or only placeholder ones); 33 document no runnable command at all.

Measured from documentation with no language model in the loop, so it is not
subject to the extraction-quality confound that limits the F1≈0.27 result. This
is the strongest standalone number the extension has.

### N3. Attribution — 5 of 11, and the mechanism matters more than the count

Of the 11 command-related artifact failures, **5 occurred in repositories that do
document a concrete evaluation command**: study003, study010, study011, study012,
study019. On the remedy axis these move `author-fix` -> `extraction-research`.

**Four of the five are OpenMMLab-family toolboxes** (mmocr, mmclassification,
mmsegmentation, Res2Net/mmdetection); study003 is also a multi-config detection
repo. This is the mechanism, and it is more interesting than the count: extraction
fails specifically where a repository ships *many* methods and configs, and the
model must select the one matching *this* paper. The workshop paper's prompt
already anticipated this ("select the configuration matching this paper's method
when the repository is a multi-method toolbox") — so this is evidence that the
mitigation did not work, which is a concrete, actionable research target.

### N4. ✗ NEGATIVE RESULT — Tier-B does not predict Level-1 outcomes

| Instrument | resolve | build |
|---|---:|---:|
| FAIR-R v1 (aggregate) | 0.584 | 0.555 |
| Software licence alone | 0.586 | 0.577 |
| **Tier-B (5 checks)** | **0.476** | **0.517** |
| Tier-B + licence | 0.549 | 0.572 |

**0.476 is below chance.** Do not soften this. Tier-B measures whether a study
documents how to reproduce a *result*; Level-1 measures whether an *environment
rebuilds*. These are different constructs and the data says so unambiguously.

Consequence for the claim: **Tier-B is validated as a descriptive instrument, not
as a predictive one.** The right outcome to validate against is Level-2 (result
reproduction), which has zero variance in this corpus — nothing reproduced. So
predictive validity is not merely untested here, it is *untestable* on this data.
The paper must say that plainly rather than implying the criteria are predictive.

What this does NOT undermine: N2 (a description of the corpus, not a prediction)
and N3 (an attribution, not a prediction). Those stand on their own.

### N5. Underpowered, do not report as a finding

Recipe outcome x documentation grade (n=17) is flat — concrete 2/2/2,
placeholder 3/2/2, none 2/1/1 across docs full/partial/absent. Suggestive of the
extractor's output being uncorrelated with documentation quality, which would be
a strong claim. **17 observations in nine cells cannot support it.** Record it as
a hypothesis for the held-out corpus, nothing more.

## O. rdip:ExecutionRecipe implemented in the ontology (17 Sept 2026)

**The gap:** the workshop paper's first contribution is "we introduce
`rdip:ExecutionRecipe`", but the term was never defined. `rag_pipeline/mapper.py`
emitted the triples; `rdip-ontology/core/rdip.ttl` defined 94 terms and not one
recipe-related. No SHACL shape. `https://w3id.org/rdip/ExecutionRecipe` resolved
to nothing. A term that is used but not defined is not introduced — and
"declared but not resolvable" is exactly what FAIR-R scores repositories down for.

**Fixed in RDIP v2.1.0** (additive only; a BNode-aware graph diff confirms the
only v2.0 triples changed are the three header version statements):

| Term | Kind |
|---|---|
| `rdip:ExecutionRecipe` | class ⊑ `prov:Plan` |
| `rdip:SetupStep` | class ⊑ `prov:Plan` |
| `hasExecutionRecipe`, `setupStep`, `requiresDataset`, `producesMetric` | object properties |
| `runCommand`, `entryPoint`, `stepOrder`, `stepCommand`, `requiresCheckpoint`, `recipeConfidence` | data properties |

**Three modelling decisions to defend in the paper:**

1. **Setup steps are a class, not repeated literals.** RDF imposes no order on
   repeated properties and setup order is load-bearing — step 3 downloads a
   checkpoint into the directory step 2 creates. `rdip:stepOrder` carries it.
   The workshop paper says "setupStep (ordered)"; with bare literals that claim
   was not actually true of the data.
2. **`requiresDataset` → `dcat:Dataset`**, not a name string, so a requirement
   resolves to a distribution and access level. A dataset released only on
   application is a reproduction blocker even when the command is perfect — and
   that is one of the 16 artifact failures.
3. **`producesMetric` → `rdip:EvaluationResult`**, reusing Section 5 rather than
   duplicating metric vocabulary, so comparing a re-run against a claim is a
   comparison of two EvaluationResult instances.

**Version IRI resolution.** `open-rdip/w3id.org` had blocks for 1.0.0 and 2.0.0
but none for 2.1.0, and the Latest block's catch-all `^/?(.*)$` matches anything
below it — so `w3id.org/rdip/2.1.0/` would have silently served *latest*. Same
content today, wrong the moment 2.2 ships: a version IRI that does not identify a
version. A 2.1.0 block is now inserted **before** the catch-all. Note the repo is
a fork; the change reaches the live service only via a PR to `perma-id/w3id.org`,
so open it early.

**Consequence for map_recipe:** it currently emits `requiresDataset` and
`producesMetric` as bare literals and `setupStep` as unordered literals. It must
be aligned to the ontology, and existing emitted recipe graphs re-mapped — cheap,
since the recipes are JSON in `data/recipes/` and need no clones.

---

## P. Journal deadline is fixed, and it reshapes the plan (29 Sept 2026)

The NGC invitation arrived. Three facts that change §J and the sequencing in
`journal_extension_plan.md`:

1. **Submission deadline 31 December 2026.** Not December 2027. The plan was
   sequenced for 4–5 months against the later date; the real window is thirteen
   weeks, nine to a professor-ready draft.
2. **Intent to submit must be confirmed by 30 October 2026 (AOE)** to
   `ijckg-2026@aiat.or.th`.
3. **The same IJCKG reviewers will be invited back.** A response-to-reviewers
   document is therefore a required submission artifact, not good practice, and
   the SRAF reviewers' specific objections are a checklist the extension is
   graded against.

The invitation names **paper #25 (SRAF) only**. The workshop paper is not
co-invited, so it is prior work to cite. N5 (cross-level linkage) survives — the
analysis is new even though it uses workshop data — but must be framed that way.

---

## Q. Single-annotator ground truth is the sharpest unaddressed objection (N9)

All 107 files under `data/ground_truth/` record `_verified_by: "First Author"`
(`_verification_depth`: 24 thorough, 83 standard). The corpus was generated by
Gemini 2.5 Flash from paper PDF + `repo_metadata.json`, then verified by one
person. **Every F1 in Table 5 is measured against that judgement**, and a
reviewer does not have to dig for this — it is in the released artifact.

This is structurally more serious than N6 (taxonomy coding, 26 cases): the
taxonomy explains a section, the ground truth underwrites every number.

Design is in `docs/annotation_agreement_plan.md`. The two points worth carrying
into the paper's methods section:

- **Plain Cohen's κ is the wrong statistic** and a methods reviewer will say so.
  The task is set-valued extraction — annotators may add items nobody proposed —
  so there is no fixed item set and no meaningful chance baseline. Report κ on
  the keep/discard decisions over the Gemini candidates (a genuine binary
  decision over a fixed set) **and** pairwise F1 on the final item sets using
  `eval_extraction.py`'s own lenient/strict matchers, so annotator agreement and
  model performance are measured against one definition of "correct".
- **Adjudication can move Table 5.** Pre-commit to reporting the corrected
  numbers as primary with a pre/post comparison. If the shift is material that is
  on-thesis, not embarrassing: it would mean single-annotator ground truth is
  itself a source of measurement error in reproducibility auditing.

**Contamination note for N3:** the ground truth was written by Gemini 2.5 Flash.
Any Gemini model in the evaluated set is being scored against a gold standard its
own family produced. Run it anyway — excluding it silently is worse — but report
it separately and label the confound. If Gemini scores materially above the
others, the gap partly measures family agreement with our own annotation, which
quantifies the contamination rather than hiding it, and ties directly to N9.

---

## R. Cost accounting is an experimental record, not just a guard (N3)

`rag_pipeline/usage_meter.py` caps spend and records per-study token cost.
Two things worth stating in the paper:

- **Per-study extraction cost cannot be reconstructed afterwards.** It is the
  input N7's selective-verification model needs, so it has to be captured during
  the run or not at all.
- Two latent bugs were found while wiring it, both of which would have defeated
  the cap: `Extractor.extract()` catches `Exception` and returns `{}`, and the
  corpus runner catches `Exception` per study and continues. A budget abort was
  therefore swallowed twice, leaving the loop calling a paid endpoint for every
  remaining study with the cap already breached. Both now propagate
  `BudgetExceeded`. This is a small but honest example of the paper's own thesis
  applied to our code: a guard that is never tested under the condition it exists
  for is not a guard.

Estimated corpus cost per model, from the actual pipeline shape (6 retrieval
queries × top_k 3, deduped to ~15 calls/study, ~850 prompt + ~300 completion
tokens, 95 studies): ≈1.2M prompt and 0.43M completion tokens. Do not report
these as measured — the three-study dry run replaces them with real figures.

---

## S. Repo-side metric extraction: what "the code can compute" means (N4)

`docs/semantic_diff_plan.md` §1.5 said three of five conflict types had no
repo-side fact to compare against. `build_harness/repo_facts.py` now supplies
datasets, hyperparameters, metrics and seeds deterministically, and
`build_harness/run_repo_facts_corpus.py` sweeps the corpus with the same
clone-to-scratch-then-delete discipline as the Tier-B sweep.

**The metric finder is the part that needed real design.** `metric_never_computed`
asks whether the code *can produce* the claimed metric, so a keyword sweep is
useless — "accuracy" appears in every README. The finder now uses four
structurally anchored signals and records which one fired:

| signal | evidence | rank |
|---|---|---|
| `metric_api` | a metrics library function or class is called (`f1_score`, `CocoMetric`, `evaluate.load("rouge")`) | 3 |
| `eval_config` | an evaluator is declared in a config (`metric=['mIoU','mDice']`) | 2 |
| `cli_flag` | a documented `--eval` / `--metric` flag | 1 |
| `logged` | the name is written to a results dict or logging sink (`results["top1"]`, `add_scalar("val/psnr")`) | 0 |

The strongest signal wins for a given metric. **Report precision per signal
class, not as one number** — a library call is much stronger evidence than a
logged string, and a reviewer should be able to see which claims rest on which.

### Three defects found by running it, all precision-damaging

1. **Acronym continuation was treated as a word boundary.** `VG → Visual Genome`
   fired on `"VGA compatible controller"` inside a GPU-detection routine; `ade`
   on `ADEQUATE`, `voc` on `VOCAB`. The naive fix — reject all trailing
   alphanumerics — breaks `CocoDataset` and `CIFAR100Dataset`, which are the
   mm-family convention and genuine facts. The rule now admits a trailing
   uppercase letter only when it opens a CamelCase word.
2. **Python docstrings and comments counted as config facts.** `COCO` was
   recorded as a dataset study080 uses, from a docstring describing OwlViT output
   format. `.py` means `source_kind` says "config", but a docstring is prose in
   exactly the way a README is. Comments and triple-quoted blocks are now blanked
   (blanked, not deleted, so evidence line numbers stay correct) while ordinary
   string literals survive — `default="prompt_templates/imagenet_templates.py"`
   is a real fact.
3. **A metric list yielded only its first element.** `metric=['bbox','segm']` is
   the standard detection setting; mask AP was being dropped silently.

Also added the mm-family metric surface forms (`bbox` → mAP, `segm` → Mask AP,
`mDice`, `mAcc`, `aAcc`), which the original alias table lacked entirely.

`FACTS_VERSION` 6 → 8. The corpus sweep is version-stamped, so a study written by
an older version is re-run rather than left to mix extractor versions in one
corpus — a discipline worth stating in the artifact appendix (N8).

### Open question, and a possible finding

On the first 9 studies, metric coverage went from 1/6 to 3/9 studies with at
least one computable metric. **Six of nine still report zero.** Two readings, and
the full 96-study sweep plus a manually checked sample must decide between them
before any of this is written up:

- a remaining detector gap, or
- a genuine property of the corpus — most repositories do not expose metric
  computation in any machine-identifiable form.

If the second holds, it is directly on-thesis: it would mean
`metric_never_computed` is undecidable for most artifacts not because the
detector is weak but because the evaluation code is absent or opaque, which is a
stronger statement about artifact quality than the conflict type itself was
designed to make. **Do not assume which it is.** Sample and check.

---

## T. N4 built and run on the corpus — numbers to quote (30 Sept 2026)

Everything here is from the authoritative sweep. **Provenance:** all 96 records
`facts_version 9`, `host skynetcpu` (ASL), `swept_at 2026-09-29`, every record
carrying the `repo_commit` it was cloned at, 0 clone failures. The Mac-produced
development sweep was discarded; nothing below comes from it.

### T.1 What exists now

| component | file |
|---|---|
| repo-side facts (deterministic) | `build_harness/repo_facts.py` (FACTS_VERSION 9) |
| corpus sweep | `build_harness/run_repo_facts_corpus.py`, `repo_facts_corpus.sbatch` |
| paper↔repo diff | `sre_engine/paper_repo_diff.py` |
| aggregation | `analysis/repo_facts_summary.py` |
| audit tooling | `analysis/metric_audit.py` |
| outputs | `validation/repo_facts/*.json`, `validation/diff_<slug>.json`, `analysis/repo_facts_corpus.json` |

### T.2 Corpus coverage — what the repo side can support at all

| fact | studies with ≥1 |
|---|---|
| hyperparameters | 81/96 (84.4%) |
| seeds | 54/96 (56.2%) |
| datasets | 49/96 (51.0%) |
| metrics | 47/96 (49.0%) |

Metric detections by signal: `metric_api` 60 (56.6%), `logged` 23 (21.7%),
`cli_flag` 12 (11.3%), `eval_config` 11 (10.4%). **Report precision per signal
class, not pooled** — a library call is far stronger evidence that code computes
a metric than a name in a log line.

Most common datasets: ImageNet 21, COCO 18, PASCAL VOC 14, C4 14, Cityscapes 9,
Visual Genome 8, CIFAR-10 7.

### T.3 ★ Conflict counts are dominated by the extractor, not the artifact

The repo side is byte-identical across the three columns, so every difference is
the extractor. This is a controlled comparison and it came free from running all
three slugs.

| | Qwen-14B | Llama-8B | Mistral-24B |
|---|---|---|---|
| hyperparameter_mismatch | 41 | 48 | 51 |
| metric_never_computed | 16 | 27 | 20 |
| **seed_mismatch** | **6** | **31** | **8** |
| dataset_mismatch | 3 | 4 | 4 |
| seed decidable | 7/95 | **38/95** | 9/95 |
| studies claiming a seed | 9/95 | **52/95** | 11/95 |
| seed values emitted | 16 | **100** | 11 |
| unmapped paper names | 637 | **1102** | 622 |

Llama-3.1-8B claims a random seed in 52 of 95 papers where Qwen finds 9, emitting
100 values against 16; its most frequent are 5, 4 and 0 — small integers, the
signature of fabrication.

**This is the direct answer to R1's sharpest question** ("how can one eliminate
that this is caused by poor LLM performance?") and it is stronger than conceding
the confound: it quantifies it. Consequence for the paper: **the diff must always
be reported per extractor and never pooled.**

`dependency` is decidable in **0/95 for all three models**. Neither side reliably
pins versions — papers cite rather than pin, and `software_dependencies` mostly
carries empty version strings. State this rather than quietly dropping the
conflict type: version-conflict detection is not achievable at corpus scale with
current data.

### T.4 ★★ The open-vocabulary ceiling — the strongest new finding

Claimed metric names matched against `METRIC_ALIASES`:

| | mentions | unrecognised | distinct unrecognised |
|---|---|---|---|
| Qwen-14B | 486 | 82.1% | 276 |
| Llama-8B | 759 | 81.2% | 397 |
| Mistral-24B | 425 | 80.2% | 279 |

**Within two points across three model families and sizes.** If this were
extraction noise the rate would track extractor quality — and Llama, which we
just showed hallucinates seeds five-fold, is marginally *better*. 114 distinct
names are unrecognised by all three independently, which removes the noise
confound by construction. 79% of distinct names appear exactly once: the
signature of an open vocabulary.

Three causes are currently pooled inside that 82% and **must be separated before
this is written up**:

1. **Recoverable by normalisation.** `ap 50`, `ap50`, `ap0.50`, `ap 75`, `ap75`,
   `ap0.75` — one metric in six surface forms. A bug, not a vocabulary problem.
2. **Extraction noise.** `performance`, `time / shower [s]`, `trr (ours)` — table
   headers and footnote fragments lifted as metric names.
3. **Genuinely open vocabulary.** `IDMUSHRA score`, `CLIP-H text-alignment
   score`, `run time for preprocessing vahadane stain norm`. Real, paper-specific,
   unmatchable in principle.

**The claim to make:** deterministic conflict detection on claimed metrics has a
ceiling imposed by open-vocabulary naming in ML papers, and that ceiling sits on
the **paper side**, not in the repository detector. This is a limit on what this
class of tooling can achieve — a statement about the field, which is the register
the journal thesis needs.

### T.5 Metric audit — an honest partial result

Ten of the 49 zero-metric studies were hand-audited against the recorded
`repo_commit` (sample fixed by seed before looking). Verdicts: **0 detector_gap,
4 genuinely_absent, 6 unclear.**

The 60% unclear rate means the audit did not settle the question. Cause: the
worksheet offered three labels and no decision rule, so "unclear" absorbed
everything ambiguous. If re-run, use a concrete test — *does any code path
compute a number that is then printed, written to disk, or returned as a
result?* — yes / no / cannot-tell-in-three-minutes.

Worth reporting anyway: study066 claims COCO AP and box mAP with no
evaluation-shaped file in the repository at all.

**Do not re-run this before T.4 is resolved.** The audit asks whether our
repo-side detector is weak; T.4 shows the binding constraint is elsewhere.

### T.6 Defects found by running against real repositories

Each was found by execution, not review, and each would have damaged N4's
precision:

1. **Acronym continuation treated as a word boundary.** `vg` → Visual Genome
   fired inside `"VGA compatible controller"`; `ade` inside `ADEQUATE`. The naive
   fix (reject all trailing alphanumerics) breaks `CocoDataset` and
   `CIFAR100Dataset`, the mm-family convention — caught by the existing tests.
   The rule now admits a trailing uppercase letter only when it opens a CamelCase
   word.
2. **Python docstrings and comments counted as config facts.** `COCO` was
   recorded as a dataset study080 uses, from a docstring about OwlViT output
   format. Comments and triple-quoted blocks are now blanked (blanked, not
   deleted, so evidence line numbers stay correct) while ordinary string literals
   survive.
3. **A metric list yielded only its first element**, dropping mask AP from
   `metric=['bbox','segm']`.
4. **Citation markers read as dependency versions.** `"[54]"` extracted as
   MMDetection's version; comparing it to a real pin gives a guaranteed false
   conflict.
5. **Two swallowed exceptions defeated the API spend cap** (see §R).

Suitable for the artifact appendix as evidence that the detector was validated by
execution rather than assertion.

---

## U. Reviewer themes and what answers them (30 Sept 2026)

Full mapping in `docs/reviewer_response_map.md`. Scores 1, 1, 1, 0. **The editors
will invite the same reviewers**, so these are graded requirements.

| theme | raised by | answered by |
|---|---|---|
| Why a knowledge graph / ontology at all? | **R1, R4** | argument + N4 |
| LLM extraction is an uncontrolled confound | **R1, R2, R4** | **N3** |
| Implementation opaque; artifact hard to find | R1, R4 | N8 + visibility |
| Aggregate FAIR-R does not predict | R1, R2 | **N1** |
| No result-level reproduction | R2 | workshop paper + **N5** |

**N3 is required, not optional** — three of four reviewers named the extraction
confound.

**The "why a KG" objection cannot be answered with data**, and nothing scheduled
produces an answer. Two reviewers independently called the central design choice
unargued. The workshop camera-ready's PROV-O/graph-vs-file argument generalises
and should become a full subsection; T.3's cross-extractor comparison makes it
concrete, since the diff is a query across two subgraphs of one study that would
be bespoke code in a JSON pipeline. **Draft this early — it is the one objection
no experiment closes.**

**On the artifact, checked against the source rather than trusting R4.** The link
is NOT missing: `SRAF/main.tex` line 388 has a Data and Software Availability
section with the Zenodo citation and the GitHub URL, line 158 states the prompts
and shapes are released, and the repo README tables them. R4 missed a *buried*
pointer — an unnumbered `\subsubsection*` after the conclusion. Treat it as
seriously as an absence: the effect on the reviewer was identical, in a paper
about reproducibility. Fix by visibility — first-page footnote, inline file paths
at each first mention, prompts in an appendix.

Editorial, from R1: format the complementary sources after Fig. 2 as a list; fix
"…we walk one artifact and to end"; a general language pass.

---

## V. Schedule and open decisions (30 Sept 2026)

- **30 Oct 2026** — intent to submit, `ijckg-2026@aiat.or.th`. Hard.
- **~30 Nov** — draft to professors.
- **31 Dec 2026** — submission.

**Highest schedule risk: the second annotator.** Blocks N6 (~2 h) and N9 (~8 h),
neither can start without a person, and the annotation must land in the first
half of November so corrected numbers freeze before writing. If nobody has said
yes with a date by mid-October, cut both and move the single-annotator objection
to Limitations.

**N10 added** (`docs/n10_badged_contrast.md`): a 20-paper badged contrast group,
predictions recorded before any run. Answers the sharpest objection to 0/17 —
whether the harness works at all. Plumbing done via `SRAF_REPO_LIST`; needs the
papers selected.

Open: separating the three causes in T.4; whether to re-run the metric audit with
a decision rule; which of N2/N6/N7 survive the compressed schedule.

---

## W. Badged contrast group: how the sample is built (9 Oct 2026)

Material for the dataset-creation subsection of the contrast-group section. The
selection procedure is itself a result, because what the search returns says
something about where artifact-evaluation culture actually exists.

### W.1 What the stratum is for

The 96-study corpus produced 0 of 17 result-level reproductions. That number is
ambiguous: it could describe the population, or it could describe our harness.
The contrast group resolves the ambiguity by adding studies that an independent
party has already reproduced. If those build and run, 0/17 is a statement about
the population. If they also fail, the finding is stronger and more
uncomfortable, and it points at the harness.

The group is **added to** the 96, never substituted for them. No claim is
generalised *from* the badged set.

### W.2 Inclusion criterion

Only one badge qualifies. ACM's own definitions:

| badge | what it certifies | usable |
|---|---|---|
| **Results Reproduced** | main results obtained in a later study by a team other than the authors, **using artifacts the authors supplied** | **yes** |
| Results Replicated | independent validation **without** author materials | no |
| Artifacts Evaluated (Functional / Reusable) | a committee exercised the artifact | weak |
| Artifacts Available | a URL exists, not formally evaluated | no |

SRAF audits *the authors' repository*. A replication written from scratch
certifies the method, not the artifact, so it would make the stratum measure
something other than artifact quality.

**To verify before the final list is frozen:** ACM revised the meanings of
"reproduced" and "replicated" at one point, so a badge on an older paper may not
carry the current definition. Check the badge metadata on each paper rather than
trusting the word.

The same trap exists in ReScience and MLRC, where teams frequently re-implement
because the original code was unusable. There the check is manual: the report
must say the replicators ran the authors' code.

### W.3 Access, and why the method changed

`docs/n10_sourcing_guide.md` (1 Oct 2026) recorded that ACM badge filtering was
behind a subscription AIT did not hold, and concluded that all 20 papers would
come from ReScience.

**That constraint no longer exists.** The ACM Digital Library became fully open
access in January 2026, roughly 600,000 papers, with badge faceting available to
everyone. ACM is therefore back in scope, and the sourcing guide's limitation
paragraph is superseded.

Record the access date in the paper. Selection from a live index is
time-dependent, and a reader repeating the search later will get a different set.

### W.4 The first search, and why it failed

Query: `"machine learning" AND "Results Reproduced"`. Twenty hits, collected
into `validation/repo_list_badged.csv`.

The DOI prefixes resolve to ASPLOS, ISCA, EuroSys, SIGCOMM, SIGMOD, CGO and
MMSys. Two confirmed via Crossref:

- `10.1145/3620666.3651367` — *ProxiML: Building Machine Learning Classifiers
  for Photonic Quantum Computing*, ASPLOS 2024
- `10.1145/3579371.3589049` — *ArchGym: An Open-Source Gymnasium for Machine
  Learning Assisted Architecture Design*, ISCA 2023

These are systems and architecture papers that *use* machine learning. The 96
are machine learning research papers, mostly vision and NLP, drawn from Papers
with Code.

**The confound.** Such a group differs from the corpus on two dimensions at
once: badged versus unbadged, and systems versus ML. If the badged set builds
more often, the obvious counter-explanation is that systems artifacts are
packaged differently, not that badging means anything. The comparison would not
support the claim it exists to support.

One row is also not ACM at all: `badged007` is `10.1109/SCW63240.2024.00166`,
an IEEE DOI. IEEE does not issue ACM badges.

### W.5 The sampling frame is itself a finding

Worth stating in the paper rather than hiding in a limitation.

Artifact badging is concentrated in communities that run artifact evaluation:
systems, architecture, programming languages, databases, networking. The venues
that publish the machine learning research our corpus is drawn from — NeurIPS,
ICML, ICLR, CVPR — **do not operate ACM badging at all**. The phrase "machine
learning" in the ACM index therefore retrieves ML-as-tool papers, not ML-as-
subject papers.

So the population of independently reproduced ML research papers is small, and
it is small for a structural reason: the field with the loudest reproducibility
discourse has the least formal artifact certification. That observation is on
thesis. It belongs next to the variance-audit result, because both say the same
thing in different registers — the instruments and institutions built to assure
reproducibility are not aimed where the problem is.

### W.6 Corrected search protocol

**Vocabulary.** Do not query the phrase "machine learning". Query the task, the
way an ML paper writes it. Each term is a separate search with the Results
Reproduced facet set, and the results are unioned and deduplicated by original
paper:

```
"image classification"    "object detection"      "semantic segmentation"
"language model"          "neural machine translation"
"graph neural network"    "recommender system"    "collaborative filtering"
"dense retrieval"         "learning to rank"      "contrastive learning"
"self-supervised"         "reinforcement learning"  "speech recognition"
```

**Venue scope.** ACM venues that both publish ML research and run artifact
evaluation: **SIGIR** and **RecSys** first (both have explicit reproducibility
tracks and ordinary Python artifacts), then KDD, The Web Conference, CIKM, ACM
Multimedia, FAccT, and the journals TOIS, TORS and TIST. Venue plus badge facet
alone may be sufficient without keywords.

**Per candidate, stopping at the first failure:**

1. Badge is Results Reproduced, under the current definition.
2. For ReScience and MLRC rows, the report states the replicators ran the
   authors' code.
3. The original repository resolves and is the one the paper points to.
4. The original paper PDF is retrievable.
5. Year and subject are close to something in the 96. Record which in
   `matched_to`.

Note that `repo_url`, `paper_url_pdf` and `arxiv_id` are the **original
paper's**, never the replication report's. Getting this backwards would audit
twenty replication repositories and answer nothing.

### W.7 Mixed sources are acceptable, padding is not

If the venue-scoped ACM searches do not yield enough ML-research papers, do not
refill the set with systems papers. That reinstates the confound. Mix sources
instead: ACM for what it gives, ReScience and MLRC for the remainder, with
`badge_source` recorded per row and the split reported in the paper.

Fifteen well-matched papers from two sources are more defensible than twenty
from one source where half are architecture work. `n` is not doing statistical
work here (see W.8).

### W.8 Threats to validity for this stratum

- **Domain confound.** Residual even after venue scoping. State the venue
  distribution of both groups in the paper and let the reader judge.
- **Selection.** The set is assembled by one person from a live index. The
  queries, facets and access date must be reported so the search is repeatable
  in principle, while acknowledging the index moves.
- **Sample size.** n ≈ 20, descriptive comparison only, no significance
  testing. Predictions were recorded in `docs/n10_badged_contrast.md` before any
  run and must be read before the results, not after.
- **Badge semantics drift.** See W.2.
- **Reproduction scope.** Build-level outcomes are in scope before 31 December.
  Result-level reproduction of the badged set is not: it needs GPU time the
  schedule does not have, and the wording "build and reproduce" on the progress
  deck overstates what will be delivered.

### W.9 Current state (9 Oct 2026)

`validation/repo_list_badged.csv` holds 20 rows carrying `study_id` and
`paper_url` only. `repo_url`, `paper_url_pdf` and `paper_title` are empty on
every row, so nothing is runnable yet. Badge provenance columns are empty except
row 1, which still holds template placeholders.

Open: whether to reframe the stratum as "communities with mature artifact
evaluation" and keep the systems papers, or re-run the search under W.6 and
narrow to ML research. The second is preferred. The decision gates the sweeps,
which must run before the GPU access ends on 30 October if the badged papers are
to be extracted with the same three open-weight models as the 96.

---

## X. N2 cross-instrument variance audit

### X.1 Why the analysis was split (16 Oct 2026)

N1 was written against FAIR-R's own output shape: a 100-point budget, three
graded levels, and a `recommendations` list that records gaps rather than
scores. None of that transfers. F-UJI has 17 metrics and no budget, howfairis
has 5 binary checks, the ML Reproducibility Checklist is scored by hand.

`analysis/criterion_validity.py` is therefore now a thin N1-specific wrapper.
The instrument-neutral parts moved to `analysis/audit_core.py` (Firth,
BH-FDR, the variance audit) and `analysis/instruments/` (one adapter per
instrument). Outcomes moved to `analysis/outcomes.py`, because resolve and
build results belong to the corpus rather than to any instrument, which is
what makes N2 a comparison of instruments rather than of pipelines.

The refactor moved no numbers. `analysis/criterion_validity.md` and
`criterion_table.csv` are byte-identical before and after, verified by diff on
both invocation paths, and `tests/test_audit_core.py::test_sraf_regression_pin`
fails if 57.8/100, 6-of-15 or the three usable criteria ever change.

### X.2 The comparable statistic is criteria, not points

Only a weighted instrument has a point budget, so "57.8% of the budget is
invariant" has no counterpart in howfairis. The figure that compares across
instruments is the proportion of criteria with zero observed variance. The
reporter prints the point-weighted figure where the instrument defines one and
suppresses it elsewhere rather than inventing a denominator.

### X.3 Correction: SRAF's saturation is mostly FLOOR, not ceiling

This changes the framing used in earlier planning and should change the
wording in the extension.

The audit now records *why* each invariant criterion is invariant. For FAIR-R
on the 96 repositories, of the 9 invariant criteria:

- **floor (6)**: Landing page, Data licence, Access level, Workflow language,
  Related links, Community standard. No repository satisfies them.
- **ceiling (2)**: Access protocol, Commit + versioning. Every repository does.
- **mid (1)**: Computational environment (R1), partial for all 96.

So the dead weight is not "criteria so easy that everyone passes". It is
largely criteria that *no* ML repository satisfies, because they describe
deposited datasets in a repository with a landing page, not code on GitHub.
That is a scope mismatch between FAIR-R's inherited FAIR vocabulary and
executable research artifacts, and it is a stronger and more specific claim
than the one N1 currently makes.

It also sharpens the N2 hypothesis. If other instruments saturate at the floor
on the same criteria, the argument is about the FAIR vocabulary rather than
about SRAF. The earlier assumption that floor saturation would only appear
when a dataset tool is misapplied to software was wrong: it is already present
inside FAIR-R.

### X.4 Instrument choice

howfairis is the headline second instrument, not F-UJI. It assesses a source
code repository against the five fair-software.eu recommendations, which is
what this corpus is. F-UJI resolves a PID and scores metadata richness from
DataCite, re3data and landing pages; a GitHub repository exposes none of that,
so F-UJI over the full corpus would floor-saturate for reasons of scope and
the invariance would be an artifact of the choice of tool. F-UJI stays in the
paper scoped to the studies carrying a Zenodo DOI, where it is in scope, with
the exclusion stated.

One caveat to print rather than discover in review: howfairis' `repository`
check asks whether the software is in a public version control repository, and
every study here was sampled because it has a public GitHub repository. That
criterion is invariant by construction. The reporter labels it `structural`
and it is kept in the table, since dropping it would flatter the instrument.

### X.5 Current state (16 Oct 2026)

Core, adapters, reporter, collector and tests are in place; 234 tests pass.
howfairis is cached for 4 of 96 studies only. The collector is resumable and
the remaining 92 need `APIKEY_GITHUB`, because unauthenticated GitHub allows
60 requests per hour and howfairis spends several per repository.

howfairis pins `click<8` and will downgrade a shared environment, breaking
camelot-py and magika. It must be installed in its own virtualenv; the
collector refuses to run and says so if imported from an interpreter that does
not have it.

---

## Y. External corroboration: the biodiversity deep-learning audit (5 Nov 2026)

### Y.1 What the source is

Ahmed et al., "Evaluating the method reproducibility of deep learning models
in biodiversity research", PeerJ Computer Science, `10.7717/peerj-cs.2618`.
The released supplement (`10.7717/peerj-cs.2618/supp-1`, file `Final_data.csv`)
was obtained and checked directly; its ten variables sum to 579 positives out
of 1000, which matches the figure printed in the article, so the file is the
dataset the paper reports on.

Population: 100 publications, 2015 to 2021, found by a Google Scholar query
joining biodiversity terms with "Deep Learning" (over 8000 hits), then
screened. The `no` column runs non-contiguously from 1 to 191, so the hundred
are the survivors of a screen over roughly 191 candidates, not a raw sample.
Describe the provenance that way if we cite it.

Each publication is hand-coded by domain experts on ten binary variables,
rolled up into four category flags and a five-level ladder. Their reported
initial inter-annotator agreement is Cohen's kappa 0.57, before they refined
the variable definitions.

### Y.2 It cannot serve as an out-of-domain corpus, and the reason is the link, not the domain

The file carries a DOI for every publication (99 via doi.org, 1 AJOL link), so
the paper side is fully identified. The repository side is not: `Source Code`
is a bare y/n with 30 positives and there is no URL column anywhere in the
file. Our inclusion gate needs a paper paired with a resolvable public
repository, so the thirty would have to be recovered by hand, one paper at a
time.

Publisher split of the thirty, which decides how much of that recovery is
behind a paywall:

| Publisher group | With code |
|---|---:|
| Wiley, mostly Methods in Ecology and Evolution (10.1111) | 8 |
| MDPI | 6 |
| Frontiers | 3 |
| Elsevier | 3 |
| Biodiversity Data Journal | 2 |
| Oxford | 2 |
| PLoS, Sci Rep, BMC, PNAS, ACM, PCI (1 each) | 6 |

Roughly 15 of the 30 are open access. Even granting full recovery, these are
2015 to 2021 ecology artifacts and our gate requires a declared environment
file; expect 10 to 15 through the gate and fewer than that to build. Too small
for a rate to sit beside 45 of 86.

The domain objection is weaker than it first looks but still holds. This is
deep learning applied to biodiversity, so the provenance shape is unchanged:
dataset, activity, model, metric. It does not exercise RDIP's
schema-independence. What it *does* contain is more stack variety than our
arXiv corpus has (an explicitly reproducible R workflow, Google Earth Engine
pipelines, LiDAR point-cloud segmentation, acoustic toolkits, a phylogenetics
tool), none of which is a `pip install -r requirements.txt` repository. So it
is a real stress test of recipe synthesis and not of the ontology.

**Decision:** cite it, do not ingest it. If Objective 3 needs more teeth than
citation gives, hand-recover the thirty and run a *qualitative* probe: report
which recipes the engine could not synthesise and which fields extraction
missed on an R or GEE repository, with no rate attached. Ten studies with a
written account of the failures answers the schema question better than a
percentage over fifteen.

### Y.3 Numbers to quote

| Variable | y of 100 |
|---|---:|
| Methods | 100 |
| Model architecture | 96 |
| Open source frameworks or environment | 88 |
| Evaluation metrics | 85 |
| Hyper-parameters | 77 |
| Dataset | 50 |
| Source code | 30 |
| Averaging result | 29 |
| Software and hardware specification | 21 |
| Randomness | 3 |

Five-level ladder: 22, 12, 4, 1, 1.

`Methods` is y for all 100 and therefore carries no information. Leave it out
of any comparison we draw with FAIR-R; quoting it would flatter their
instrument the way the howfairis `repository` check flatters ours (see X.4).

### Y.4 ★ The conjunction, which is the strongest thing in the file

Of the 30 publications that released code: 28 also report hyperparameters, 23
also release data, 15 also give a hardware specification, 3 report randomness,
and **exactly 1 publication out of 100 has all five**.

This is their equivalent of our 26 tier-full studies, and it is a harder number
because it was reached by a human reading the paper rather than by a
file-presence heuristic. It is the external answer to the reviewer who thinks
our 96-study corpus is unusually bad: an independent group, different field,
different method, same conclusion.

### Y.5 Two findings that corroborate ours directly

**Seeds.** Randomness is y for 3 of 100. We have 27 seed fields across 1627
annotated items. Two sources, two methods (hand coding by domain experts
versus tool extraction), same result. This is the single best external support
for the seed claim and it should go in the discussion, not just related work.

**Environment versus framework.** Open source frameworks or environment is 88
of 100, but software and hardware specification is 21 of 100. People name
PyTorch and then say nothing about what they ran it on. That is exactly the
distinction `rdip:ComputingEnvironment` versus `rdip:EnvironmentSpec` exists to
make visible, and it is the first external number I have found that separates
"named a framework" from "declared an environment". It supports the N1/X.3
floor-saturation argument from a completely different direction: their
instrument finds the same gap that our Computational environment criterion sits
at partial-for-all-96 on.

**Agreement benchmark for N9.** Their initial kappa of 0.57, before definition
refinement, is a published external expectation for what this kind of coding
task achieves on a first pass. It is a useful anchor when we report our own
agreement, and it argues for the frozen codebook and screening test rather
than against them.

### Y.6 Cautions before any of this is cited

- FAIR is not mentioned anywhere in their work. Do not present it as a FAIR
  study; it is a method-reproducibility study that happens to overlap our
  Reproducible dimension.
- Their gold standard is Heil et al. (2021), reproduction "with the execution
  of a single command". Worth noting as a comparison point to our build/resolve
  split, but it is a stricter and narrower target than ours.
- Coverage ends at 2021, so it says nothing about the period in which
  environment-declaration practice changed. Any trend claim we make from our
  2019 to 2025 window cannot be supported or contradicted by it.
- They themselves flag that the sample "may not be entirely free from bias"
  and that manual curation forces the small n. Say so when we cite them.
- **Licence of the supplement is unverified.** The PeerJ article page states no
  licence for `supp-1`. Confirm before we reproduce any part of their table
  verbatim, and before the CSV goes anywhere near the public repository. For
  now the file lives outside the repo and the numbers above are recorded here
  so the draft does not depend on it.
- Authors, year, volume and article number were not visible on the fetched
  article page. Resolve the full citation before the bibliography is frozen.

---

## Z. N9 rescoped: 12 gold studies, calibration instead of screening (9 Nov 2026)

Two changes, both made before any annotator was approached, which is what keeps
them design decisions rather than post-hoc adjustments.

### Z.1 The sample is the gold tier, taken whole

**12 studies, 1,127 items, about 5.5 hours** of annotator time, down from 20
studies and 1,627 items at 8 hours.

The 8 silver-tier studies were cut to fit the annotation budget. The cut is **by
tier, not by draw**: no study was kept or dropped on anything observed about it,
so there is no selection to defend. `evaluation/annotation_round1/SAMPLE.json` is
deliberately left untouched as the record of what was drawn under seed 20261009;
the workbook's own `SAMPLE` constant now carries the revised figures and a note
saying when and why the tier was cut. The method section should state both: 20
drawn, 12 annotated, 8 cut for budget on a stated date.

Per-field counts on the 12 gold studies, which is what decides what can be
reported:

| field | all 20 | 12 gold |
|---|---:|---:|
| methods | 485 | 349 |
| evaluation_results | 327 | 220 |
| dependencies | 324 | 216 |
| hyperparameters | 233 | 159 |
| datasets | 191 | 143 |
| environment | 40 | 30 |
| random_seeds | 27 | **10** |
| total | 1,627 | 1,127 |

Two consequences to print rather than let a reviewer find:

- The agreement estimate covers the **gold tier only**. Do not claim it for the
  corpus or for silver.
- The silver tier carried **17 of the 27 `random_seeds` items**, so that field
  falls to 10 and leaves the agreement study. This is acceptable because the seed
  result is a *prevalence* claim (27 of 1,627), not an agreement claim, and it is
  now corroborated externally at 3 of 100 by the biodiversity audit (see Y.5).
  Report `environment` (30) and `random_seeds` (10) as raw agreement counts with
  **no coefficient**, on the N5 precedent.

### Z.2 Screening became calibration

The ten codebook items were a qualification test with a pass mark of 8 of 10 and
a hard gate on the annotation. They are now **training with recorded first
answers**: the codebook's answer and its rationale appear as soon as the
annotator answers, the first answer is still locked and exported, and nothing is
withheld on the strength of the score.

Three reasons, in order of force:

1. **With one second annotator a pass mark was never a gate.** We would not have
   rejected the only person who said yes. A reviewer reading "pass mark 8 of 10"
   asks what happened to those who failed, and the honest answer is that there
   was nobody else.
2. **It was never a closed-book test.** The reference answers (`key`, `ev`,
   `why`) are embedded in the HTML the annotator receives. The gate was
   decorative, and removing it removes a false assurance rather than a control.
3. **The literature points at definitions, not people.** Ahmed et al.
   (`10.7717/peerj-cs.2618`) got Cohen's kappa 0.57 on the first pass and fixed
   it by refining variable definitions, not by replacing annotators. Klie et al.
   (CL 50(3), 2024) count qualification filter and qualification test as separate
   practices at 26% and 18%; we keep the filter and convert the test to training.

The declared five-criterion qualification is **unchanged** and still gates
participation. That is what answers the professor's original objection; the ten
items were always a second, different instrument.

**How to report it.** "The second annotator worked ten calibration items against
the frozen codebook before annotation began and matched the reference on *k* of
10 before feedback; the disagreements concerned *X* and *Y*. The score was
recorded and is reported here, and was not used to include or exclude anyone."
That sentence survives n = 1, which "passed a screening test" does not.

### Z.3 What changed in the files

- `docs/annotation/n9_annotation_workbook.html` → `n9-workbook-1.4`. `PASS`
  removed; `gateOK` is now completion only; result panel reworded and always
  offers Start; tab, eyebrow and copy relabelled Calibration; export key
  `screening` → `calibration_n9` with `gated:false` and `correct` → `matched`;
  `DATA` cut to the 12 gold studies. Verified with Playwright: 18 checks,
  including that a score of 0 of 10 still unlocks the annotation.
- `docs/annotation/README.md` → twelve folders, 5.5 hours, batch wording.
- `docs/annotation_agreement_plan.md` → revised sample block, per-field counts,
  the calibration rationale, and the time table.
- `evaluation/build_annotation_bundles.py` still has `N_SILVER = 8`. **Do not
  change it.** The bundles for all 20 are already built and the constant is the
  record of how they were built; the cut is applied downstream, by which folders
  are sent. If the bundles are ever regenerated, set it to 0 then and say so.

### Z.4 The agreement statistics are pinned before the data (9 Nov 2026)

`analysis/n9_agreement.py` with `tests/test_n9_agreement.py`, 12 tests, written
and run before any second annotator exists. The point of writing it first is
that a disagreement with the numbers later cannot be settled by adjusting the
estimator.

Four decisions are fixed in code:

- **`MIN_FIELD_N = 50`.** A field gets a coefficient only above 50 jointly
  decided rows. At n = 30 and p = 0.26 the bootstrap interval on kappa spans
  roughly +/-0.25, which cannot distinguish good agreement from poor. On the 12
  gold studies this admits methods, evaluation_results, dependencies,
  hyperparameters and datasets, and excludes environment (30) and random_seeds
  (10). The threshold was set from the counts, before the labels existed.
- **Unsure leaves the denominator.** `U` means the annotator declined to
  decide, not that they chose a third category. Counting it as a label inflates
  the number of categories and deflates chance agreement. Unsure rows are
  reported as a separate count and queued for adjudication.
- **Both coefficients, always.** Cohen's kappa and Gwet's AC1 side by side,
  because the keep prevalence is about 26% and that is where the kappa paradox
  bites. The self-test demonstrates it: at 10% disagreement held constant,
  prevalence 0.50 gives kappa 0.816 and AC1 0.816; prevalence 0.26 gives 0.763
  and 0.842; prevalence 0.05 gives **0.419 and 0.858**. Where the two diverge
  in the real data, that divergence is the finding and both are printed.
- **Additions are never folded into a coefficient.** A row an annotator adds
  has no counterpart judgement, so it is scored as precision and recall against
  the other annotator's additions.

A degenerate-field flag was added after the tests caught an asymmetry worth
reporting rather than hiding: if one annotator uses a single label throughout,
Cohen's pe is 1 and kappa is undefined, while Gwet's pe is 0 and AC1 is exactly
1.0. AC1 is arithmetically right and the agreement is real, but no
discrimination has been demonstrated, so the report marks the field and says so
beside the number rather than printing a bare `AC1 = 1.000`.

The report also emits the **calibration diagnostic** promised in Z.2: for each
field, the number of calibration items, how many the annotator first missed,
and that field's disagreement rate in the real annotation relative to the
overall baseline. It is explicitly not a statistic (ten items over seven fields
cannot support one). It answers one question: did the codebook rules on which
the annotator and the codebook first diverged go on to produce disproportionate
disagreement? A yes points at the rule's wording, a no says the calibration
miss was noise. Either answer is worth a sentence, and it is what stops the
calibration score sitting alone in the method section with no work to do.

---

## AA. Two bookkeeping corrections, and one false alarm (9 Nov 2026)

### AA.1 The "31 planted placeholder rows" claim does not exist

Flagged earlier as an unsupported claim on corpus deck slide 3 and in the
committee memo. It is not there. Searching both documents, the only "31" is
**31 December**, the submission deadline, in an action-table row. The flag was a
misreading on our side and is withdrawn, so nothing in the deck or the memo
needs correcting on this point.

Two real things sit nearby and were being conflated with it:

- `placeholder_recipe` is an **observed** failure mode, not a planted one: an
  extracted run command containing an unfilled placeholder. It accounts for 7 of
  the 26 taxonomy rows. `_clean()` in `build_annotation_bundles.py` *removes*
  schema placeholders the extractors emit; it plants nothing.
- `evaluation/inject_conflicts.py` genuinely does plant things, but they are
  **conflicts** for the N4 paper-to-repository detector, with an equivalences
  half so that recall is not rewarded for firing on everything. That is a sound
  and separate contribution and should not be described as planted placeholders.

### AA.2 "26 buildable repositories" is wrong wherever it appears

Section E of these notes and the committee memo at the paragraph answering the
paper-to-code divergence question both say "the 26 buildable repositories". The
set is right and the word is wrong, which is the same error the memo corrects
four paragraphs earlier about the IJCKG abstract.

Verified against the data: `final_tier == "full"` is 26 studies in
`analysis/predictor_table.csv`, and `result_repro/manifest.yaml` contains
exactly those 26 (overlap 26 of 26). So the 26 is the **collection-tier
stratum** that the result-reproduction experiment was scoped to, defined by
declared environment information scoring 5 or above *before anything was built*.
The number that built is **45 of 86 attempted**, a different and larger set.

Correct phrasings: "the 26 studies in the result-reproduction stratum" or "the
26 full-tier studies". Never "buildable", and never "reproduced".
Section~6.2 of the draft now states this explicitly, including that we made the
misreading ourselves, because a reader meeting 26 and 45 in adjacent sections
will otherwise assume one is a subset of the other.

### AA.3 `melo2025ppmontology` authors confirmed

Melo, H\'ector; Avila, Oscar; Villamil, Mar\'ia del Pilar. Procedia Computer
Science 256, 1649--1657, 2025, `10.1016/j.procs.2025.02.302`, CC BY-NC-ND 4.0.
Confirmed from the Crossref record, not reconstructed. The `key =` sort
workaround is removed and the `doi` field no longer carries a `https://doi.org/`
prefix. The bibliography now has no author-less entry.
