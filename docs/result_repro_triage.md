# Result-level reproduction — triage & run plan (WS1)

The 26 full-tier repos are **not** equally runnable. Triaging them is part of the
result: the paper reports the funnel (build → run → result-match) and a **taxonomy
of what blocks result-level reproduction**. Below, each repo is marked
**RUN** (attempt it), **HEAVY** (runnable only if the large dataset is staged), or
**SKIP** (with the blocking reason).

Start with the RUN tier (small/standard data, fast), then HEAVY as datasets allow.

---

## Tier A — RUN first (small/standard data, single GPU, fast)

| study | repo | metric (claimed) | data | what to run (confirm in README) |
|---|---|---|---|---|
| study002 | dice-embeddings | MRR = 0.1 | KGE benchmarks (FB15k-237 / WN18RR / UMLS) — ship in repo, tiny | train+eval a Kronecker/Keci model on the named dataset; read MRR off the eval log |
| study003 | RCOD | S-measure (S_alpha) = 77.0 / 81.1 | COD10K / CAMO / NC4K (~few GB) + provided checkpoint | run the test/eval script with the released checkpoint; read S-measure |

## Tier B — RUN next (medium data / setup)

| study | repo | metric | data | notes |
|---|---|---|---|---|
| study021 | dpl (SGG) | mR@50 / mR@100 | Visual Genome (~few GB) + GloVe + checkpoint | Scene-Graph-Benchmark eval; VG setup is fiddly |
| study006 | l-map | Average Score (±) | RL envs bundled | scores are stochastic — the ± band matters for tolerance |
| study024 | ccvm | objective_value = -1029.5 | small / synthetic (optical-network QP) | niche solver; may run on CPU quickly |
| study025 | vfa | DSC | OASIS / IXI registration (moderate) | **claimed value is non-numeric ("mean of 132 labels") → cannot auto-compare**; needs a concrete number to score |

## Tier C — HEAVY (mmlab-style; clear `tools/test.py` eval, but big data)

Runnable via `python tools/test.py <config> <checkpoint> --eval <metric>` once the
dataset + model-zoo checkpoint are staged.

| study | repo | metric | dataset (size) |
|---|---|---|---|
| study009 | mmpose (HigherHRNet) | AP = 70.5 / 67.6 | COCO keypoints (~19 GB) |
| study019 | Res2Net/mmdetection | mAP = 39.2 | COCO detection (~19 GB) |
| study026 | CSE-Autoloss | mAP = 38.5 / 37.2 | COCO detection |
| study012 | mmsegmentation (Panoptic FPN) | PQ = 40.9 / 58.1 | COCO panoptic |
| study010 | mmocr (SVTR) | acc | text-recognition sets |
| study014 | mmdetection3d (H3DNet) | mAP = 67.2 / 60.1 | ScanNet / SUN RGB-D (heavy prep) |
| study018 | WheatDet / RetinaMask | mAP | COCO — **check repo↔paper match** |
| study011 | mmclassification (RepVGG) | top-1 > 80% | **ImageNet (~150 GB) → likely SKIP on storage** |

## Tier D — LOW / uncertain

| study | repo | why low |
|---|---|---|
| study007 | DeepRL | "Average variance" is noisy; hard to match a point value |
| study008 | tight-budget-llm-adaptation | LLM train/eval, likely multi-GPU / long |
| study020 | csaw-m | CSAW-M mammography data is **access-gated** (application) |

---

## SKIP — with the blocking reason (this list *is* a finding)

| study | repo / paper | reason (blocker category) |
|---|---|---|
| study001 | DeepSpeed / ZeroQuant-V2 | PPL on **BLOOM-176B / OPT-66B** — far beyond 1×48 GB GPU → *out of compute scale* |
| study004 | irc-url-title-bot / "Mathematics of Deep Learning" | repo is an IRC bot — *repo↔paper mismatch* |
| study005 | cross-domain-compositing / eDiff-I | no claimed number **and** repo≠paper — *mismatch / no claim* |
| study013 | zenodo/zenodo / COOS benchmark | repo is the Zenodo platform — *repo↔paper mismatch* |
| study015 | FTHM-Solver | no numeric claim captured — *no claimed value* |
| study016 | avalon | "steps per second" — *hardware-bound throughput, not a claim* |
| study017 | histocartography | "Processing Time" — *hardware-bound timing* |
| study022 | FuxiCTR / TransAct | "REPIN/CLICK gains %" — *production A/B metric, not repo-reproducible* |
| study023 | modelscope-agent / Mobile-Agent-v2 | needs a **mobile device/emulator + VLM API** — *not cluster-reproducible* |

**Blocker taxonomy (for the paper):** out-of-compute-scale · repo↔paper mismatch ·
no numeric claim · hardware-bound metric (throughput/time) · production/online metric ·
external-device/API dependency · access-gated data. These explain *why* a repo that
builds still can't be result-reproduced.

---

## Expected funnel (honest framing)

Of 26 buildable repos: ~9 are un-runnable for the reasons above, ~3 are low/gated,
and ~14 are attemptable (2 easy, 4 medium, ~8 data-heavy). Realistically we run the
Tier A/B set + whatever COCO-based Tier C we can stage, and report **how many of the
*runnable* repos reproduce their headline number within tolerance**. Even 5–8 clean
runs make a strong, honest result — and the SKIP taxonomy is a contribution on its own.

## Next actions
1. Stage & run **study002** and **study003** first (smallest, fastest).
2. Set the SKIP rows in `manifest.yaml` (done via script) so only ~14 need commands.
3. Fill `run.command` per runnable repo from its cloned README, then
   `sbatch --export=ALL,STUDY=studyNNN result_repro/run_result.sbatch`.
