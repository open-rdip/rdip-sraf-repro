# Journal Extension (Paper B) — Plan

**Goal.** Extend the IJCKG paper into a journal paper by finishing the remaining
proposal questions: **RQ2** (semantic diff / conflicts detectable before re-run),
**RQ3** (extraction benchmark — deepen), and the new headline experiment,
**result-level reproduction** (does a buildable repo reproduce its *claimed*
numbers?). Covers proposal objectives **OB2** and **OB4**.

**Gating.** Submitting the journal is gated on the IJCKG decision / an extension
invitation. The **experiments are not gated** — they strengthen the thesis
regardless, and cluster/GPU access is time-sensitive (storage-package change), so
we run and *bank* the experiments now and write later.

---

## Contributions of Paper B

- **B1** Reproducible open-weights extraction pipeline (PDF → RDIP). *Done.*
- **B2** Human-verified extraction benchmark (gold 12 + silver). *Done.*
- **B3** Formalisation gap / extraction accuracy (RQ3). *Done; optional paid-model upper bound.*
- **B4** Semantic-diff conflict taxonomy + SHACL detection (RQ2). *Engine built; needs evaluation.*
- **B5** Result-level reproduction — the new headline result. *Scaffolding built; needs runs.*

---

## Workstreams

### WS1 — Result-level reproduction  (headline, time-sensitive)
Does a repo that *builds* actually reproduce the numbers it claims?

- **Have:** `result_repro/manifest.yaml` (26 full-tier repos, each with its
  `claimed[]` numbers), `run_result.sbatch`, `compare_results.py` (classifies
  reproduced / partial / mismatch, 5% tol).
- **Need:**
  1. Fill `run.command` + dataset-staging notes per repo (semi-manual, from each README).
  2. Run on the GPU node; record `obtained[]`.
  3. `compare_results.py` → the funnel: resolve% → build% → run% → result-match%.
- **Effort:** high (semi-manual + GPU). **Owner:** cluster (Suhel); Claude drafts the run commands.

### WS2 — Semantic diff / RQ2  (conflicts before re-execution)
Which configuration divergences can we catch by comparing graphs, before running?

- **Have:** `sre_engine/diff_engine.py` + `construct_{version,digest,seed,hardware}_conflicts.sparql`
  + `conflict_report.py`; validated on synthetic graphs.
- **Need:**
  1. Decide the *diffing scenario* — what two graphs to compare (options below).
  2. Build a small **labelled conflict set** (pairs with known divergences) for precision/recall.
  3. Run the engine over the corpus; report precision/recall per conflict type.
- **Diffing-scenario options (to pick):**
  - (a) *Paper-declared vs repo-parsed* config for the same study (do the paper and code agree?).
  - (b) *Original vs reproduction* pairs (needs reproduction graphs — overlaps WS1).
  - (c) *Injected conflicts* — take clean graphs, inject known version/seed/digest/hardware changes, measure recall (clean, controllable ground truth).
- **Effort:** medium (design + one run). **Owner:** Claude (design + driver) → cluster (run).

### WS3 — RQ3 deepening + paid-model comparison  (optional upper bound)
- **Have:** 3 open models, entity-level F1, per-field breakdown.
- **Need (optional):** run 2–3 paid API models over the ~95 papers (~$15–35) as an
  upper bound; per-field comparison table. **Gated on budget approval.**
- **Effort:** low. **Owner:** cluster/API once budget cleared.

### WS4 — Writing  (gated on IJCKG acceptance / extension invite)
- Outline Paper B; map RQ → section; assemble tables + figures from WS1–WS3.

---

## Recommended order
1. **WS1** first — highest value + time-sensitive (bank the GPU runs now).
2. **WS2** in parallel — mostly design + a quick run; option (c) is the cleanest for a defensible precision/recall number.
3. **WS3** when budget is approved (cheap, fast).
4. **WS4** once the IJCKG decision / extension path is clear.

## Immediate next step
Start WS1: draft `run.command` + dataset notes for the 26 repos (from their READMEs)
so the GPU runs can start straight away. In parallel, write the WS2 evaluation design
(recommend option (c), injected conflicts, for clean ground truth).
