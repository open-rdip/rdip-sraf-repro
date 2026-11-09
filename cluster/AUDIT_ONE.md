# Auditing one external paper on the cluster

Written for the committee request of 19 October 2026. Use it whenever a member
sends a paper and its repository and wants the score.

## Why this cannot run outside the cluster

The Cowork environment's egress policy allows package registries and GitHub, and
refuses `huggingface.co` and `generativelanguage.googleapis.com`. Without the
first, specter2 cannot download and the embedding index cannot be built. Without
the second, there is no extractor. SSH is not available either, so the cluster
cannot be driven remotely from there. Everything that does not need those two
hosts was run locally and is in the report; this job completes the rest.

## One time

```bash
# the conda env needs the embedding stack and a client library
~/envs/sraf/bin/pip install sentence-transformers google-generativeai
```

## Each paper

```bash
cd ~/rdip-sraf-repro
scp <your machine>:paper.pdf data/papers/study900.pdf   # or copy it up any way

sbatch --export=ALL,SRAF_STUDY=study900,\
SRAF_REPO_URL=https://github.com/xxhu94/CSGNN,\
SRAF_PDF=data/papers/study900.pdf \
    cluster/audit_one.sbatch
```

Use a study id outside `study001`-`study096` so the corpus is never contaminated.
`study900` upward is reserved for these one-off external audits.

## What comes back

| File | Contents |
|---|---|
| `validation/results/<study>.json` | build outcome and the FAIR-R breakdown |
| `data/extractions/<study>__<model>.json` | the extracted metadata |
| `validation/repo_facts/<study>.json` | the deterministic repository parse |
| `~/triplestore/exports/<study>.ttl` | the study graph |

Send those four back and the analysis can be finished off the cluster.

## Known results for CSGNN, from the local partial run

So the cluster figures can be checked against something.

- Artifact discovery found **no** build artifact. No requirements, environment,
  setup, pyproject or Dockerfile. `run_build_test` returns `attempted: false`.
- Repository metadata: Apache-2.0, commit `aef3136b`, identifier is the repo URL.
- Deterministic parse found 4 metrics and **zero** datasets, hyperparameters and
  seeds. All three zeros are false negatives; see the report.
- Hand scored FAIR-R estimate: **41 to 50 of 100**. If the cluster number lands
  far outside that range, something differs and is worth tracing.
- Reproduction is expected to fail even on the cluster unless `data.dgl.ai` is
  reachable: the code needs DGL 0.4+ APIs and PyPI serves only 0.1.3 from 2018.
