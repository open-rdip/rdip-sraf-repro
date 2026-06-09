# SWJ Paper — Decisions & Findings Log

Running record of methodological decisions and empirical observations from the
build-out, to seed the Semantic Web Journal paper once experiments finish.
(Session: 2026-06-09.)

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

## Infrastructure constraints (affect reproducibility-of-our-study statement)

- Storage approved: **200 GB** (not 300). Drove the streaming design: clone to
  node-local scratch -> process -> delete; only triples + results persist.
- Cluster policy: **max 1 running job, 1 node/job, 7-day max.** Corpus runs as a
  single sequential, resumable job (not a Slurm array).
- Containerless runtime: conda env (`~/envs/sraf`, call its python by abs path)
  + standalone Oxigraph binary (`~/bin/oxigraph` 0.5.8). No Apptainer on compute.

## What is built (code state)

- `build_harness/`: `artifact_finder.py` (recursive/ranked), `build_tester.py`
  (two-level resolve+build), `repo_metadata.py` (identifier/license/commit),
  `process_repo.py` (orchestrator), `run_corpus.sbatch` (single-job, resumable),
  `merge_results.py` (optional re-import).
- `lifter/parsers/docker_parser.py`: extracts author-declared `@sha256` digest.
- `lifter/mapper/rdip_mapper.py`: `map_repo_metadata()`.
- `cluster/`: onboarding scripts (containerless), `download_models.sbatch`.

## Outstanding before analysis

- GPU-node capability check (`srun --partition=ASL-gpu …`) — decides vLLM serving
  and the run-test harness.
- Model download (#4) for the RAG path.
- RAG/LLM extraction wiring -> seeds/methods/eval-results -> FAIR-R variance (RQ3,
  RQ4).
- Run-test harness for the 26 full-tier repos (result reproducibility, 0.5% tol).
- Full 96-repo corpus run (build + metadata + FAIR-R), then Phase IV stats.
