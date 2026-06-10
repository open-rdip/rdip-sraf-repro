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
  + standalone Oxigraph binary (`~/bin/oxigraph` 0.5.8). No Apptainer on compute.

## What is built (code state)

- `build_harness/`: `artifact_finder.py` (recursive/ranked), `build_tester.py`
  (two-level resolve+build, declared-Python + PyTorch index), `python_version.py`
  (declared-version resolver + interpreter ladder), `repo_metadata.py`
  (identifier/license/commit), `process_repo.py` (orchestrator),
  `run_corpus.sbatch` (single-job, resumable), `merge_results.py` (re-import).
- `lifter/parsers/docker_parser.py`: extracts author-declared `@sha256` digest.
- `lifter/mapper/rdip_mapper.py`: `map_repo_metadata()`.
- `cluster/`: onboarding scripts (containerless), `download_models.sbatch`.
- `analysis/summarize_results.py`: corpus stats → `results_summary.md/.csv`.
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
