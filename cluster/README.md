# SRAF on AIT Slurm — cluster runbook

This directory holds everything needed to stand SRAF up on the AIT Slurm
cluster and run the pipeline under the **200 GB** home-volume budget.

The guiding rule: **the 200 GB NFS home holds only durable artefacts**
(code, models, triplestore, results). Everything transient — repo clones,
build artefacts, scratch — lives on node-local `/tmp/$SLURM_JOB_ID/` and is
deleted when the job ends. This is what keeps the 96-repo corpus off the
home volume.

---

## 0. One-time facts to fill in

Before running anything, set these to match your cluster. They appear at the
top of every `.sbatch` file as `#SBATCH` directives — grep for `EDIT-ME`.

| Variable | Value to confirm |
|---|---|
| `--account` | your Slurm account/allocation name |
| `--partition` (CPU jobs) | the CPU node partition (2× EPYC, 512 GB) |
| `--partition` (GPU jobs) | the AI-node partition (RTX A6000 ×4) |
| `--gres=gpu:N` | GPU request syntax your cluster uses |
| `HOME=/home/dsai-st125286` | confirm with `echo $HOME` |

Check available partitions/accounts with `sinfo` and `sacctmgr show assoc user=$USER`.

---

## 1. Layout on the cluster

```
/home/dsai-st125286/
├── rdip-sre/                 # the repo (git clone — done once)
│   ├── cluster/              # this directory
│   └── ...
├── images/                   # Apptainer .sif files (built once)
│   ├── sraf-engine.sif
│   ├── oxigraph.sif
│   └── vllm.sif
├── models/                   # HF_HOME — model cache (~48 GB)
└── triplestore/              # durable Oxigraph store (per-study named graphs)
```

`/tmp/$SLURM_JOB_ID/` (node-local scratch) is used inside jobs for clones and
build artefacts — never the home volume.

---

## 2. Onboarding sequence

Run these in order. Each step has a script in this directory.

```bash
# --- on the login node ---
cd ~
git clone git@github.com:open-rdip/rdip-sre.git
cd rdip-sre
cp .env.example .env          # then edit .env: real OPENAI_API_KEY / GOOGLE_API_KEY

# Step 3 — build the three Apptainer images (engine, oxigraph, vllm)
bash cluster/build_images.sh

# Step 4 — cache the 3 models to HF_HOME (~48 GB) via a Slurm job
sbatch cluster/download_models.sbatch
#   watch:  squeue -u $USER ;  tail -f logs/download_models-*.out
#   verify: du -sh ~/models      # must be well under budget

# Step 5 — first end-to-end verification: lift ONE repo on the cluster
sbatch cluster/lift_one.sbatch
#   this mirrors the local `transformers` test from Block 1
#   success = RDIP triples land in a named graph
```

When `lift_one` reports triples uploaded, the cluster path is proven and the
streaming build harness (Bucket C) can be scaled across the corpus.

---

## 3. Why three separate images

- **sraf-engine.sif** — the pipeline. Lightweight, CPU-only, built from
  `containers/sraf-engine.def`. Runs the lifter, mapper, SHACL, scorer.
- **oxigraph.sif** — the triplestore, pulled from the official image, run as
  an Apptainer *instance* (background service) bound to a triplestore dir.
- **vllm.sif** — the LLM server, pulled from `vllm/vllm-openai`, run as an
  instance exposing an OpenAI-compatible API on `localhost:8000`. The engine
  reaches it via `VLLM_SERVER_URL` (already wired in `config.py`).

vLLM is deliberately **not** baked into the engine image — it needs CUDA and
is large; keeping it separate keeps the engine image small and portable, and
lets the lifter-only verification (Step 5) run with no GPU at all.

---

## 4. Storage budget (200 GB home)

| Item | Budget |
|---|---:|
| Repo + code | 2 GB |
| 3 models (8-bit) in `~/models` | 48 GB |
| 500 paper PDFs | 5 GB |
| Repo working set (streamed, transient → scratch) | ~12 GB |
| OOD repos (streamed) | 3 GB |
| Triplestore | 8 GB |
| Gold-standard + RAG outputs | 12 GB |
| Build-harness logs (rotated) | 5 GB |
| Embedding indices | 8 GB |
| Experiment outputs | 20 GB |
| Python envs (in-image, slim) | 8 GB |
| Backup / git | 8 GB |
| Safety margin | ~53 GB |
| **Total** | **200 GB** |

The corpus line (was 80 GB for 96 resident repos) is gone: the harness clones
each repo to scratch, lifts/scores it, persists only triples + results, then
deletes the clone. See `build_harness/` (Bucket C).
