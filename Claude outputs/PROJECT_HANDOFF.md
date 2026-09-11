# Project Handoff — Reproducibility Auditing & Result-Level Reproduction (PhD)

**Purpose of this file:** bring a fresh assistant/collaborator up to speed on the whole project in one read.
**Revised 9 Sept 2026** (supersedes the Sept 2026 draft). Changes in this revision are marked ⟳.

## Who / what

- **Researcher:** Suhel Acharya, PhD student, Asian Institute of Technology (AIT). Email: `st125286@ait.asia`.
- **Co-authors / advisors:** Chutiporn Anutariya (AIT), Yasuyuki Minamiyama (Univ. of Tokyo / NII), Hideaki Takeda (NII), Vilas Wuwongse (Mahasarakham Univ.).
- **Goal:** a system to **describe → measure → test** the reproducibility of machine-learning research, using a knowledge graph (RDIP) + LLM extraction. Target graduation **December 2027** (requires a journal paper **accepted**, not just submitted).

## The three papers (the spine of the work)

1. **RDIP ontology** — *Enabling FAIR Research Lifecycle Provenance: The RDIP Project-Centric Integration Profile.* **TPDL 2026 — ACCEPTED.** The ontology (project-centric integration profile) that everything else builds on.
2. **SRAF (measurement)** — *SRAF: An Ontology-Grounded Knowledge Graph Framework for Auditing the Reproducibility of Machine-Learning Research.* **IJCKG 2026 main track — ACCEPTED. ⟳ Camera-ready FINISHED and closed out.** The FAIR-R graded scoring instrument.
3. **Result-level reproduction** — *From Builds to Numbers: Engine-Driven Result-Level Reproduction of Machine-Learning Papers and a Taxonomy of Failure.* **IJCKG 2026 workshop.** ⟳ **Status: all previously-listed submit-blockers are fixed; the paper is awaiting the advisor's approval before submission.** Introduces `rdip:ExecutionRecipe`, the two-phase reproduction engine, the failure taxonomy.
4. **(Planned) Journal/platform paper** — capstone integrating all three into one open platform. Target: **Semantic Web Journal** (Tools & Systems). Needs: delineated novelty vs the three papers, a sustainable open system, and a utility/user evaluation.

## Folder map ⟳ (corrected)

| Path | What |
|---|---|
| `~/Documents/AIT/PhD/projects/rdip-sraf-repro` | **The code repo.** ⟳ Renamed from `rdip-sre`; now on branch **`main`** (not `cluster`), pushed to **`github.com/open-rdip/rdip-sraf-repro`**. LICENSE present. See its `README.md`. |
| `~/Documents/AIT/PhD/projects/rdip-ontology` | ⟳ The RDIP ontology repo (own LICENSE + README, `core/`, `imports/`, `versions/`, `evaluation/`). |
| `~/Documents/AIT/PhD/Paper Writing/IJCKG_WP` | **Workshop paper — CEUR-ART, SOURCE OF TRUTH.** `main.tex` here is the one to submit. |
| `~/Documents/AIT/PhD/Paper Writing/SRAF` | Accepted **IJCKG main paper** (LNCS `main.tex`) + slide contents + figures. Camera-ready done. |
| `~/Documents/AIT/PhD/Paper Writing/RDIP_Ontology` | ⟳ TPDL ontology paper. |
| `~/Documents/AIT/PhD/Paper Writing/IJCKG Workshop Paper` | **STALE** LNCS working copy of the workshop paper. Ignore / archive. |

## Key results (must stay consistent across paper + slides)

- **Funnel:** 96 repositories (with code) → 26 build → 17 attempted → 13 recipe extracted → 0 ran → **0 reproduced automatically**.
  - ⟳ **The corpus is definitively 96 repositories** — `validation/results/` contains exactly `study001.json`…`study096.json`, and the **accepted SRAF camera-ready says 96** throughout (abstract, intro, §4.3, Fig. 3 caption, results, conclusion, data-availability). Its canonical phrasing: *"96 machine-learning repositories with associated papers (95 with retrievable papers)."*
  - ⟳ **RESOLVED 9 Sept 2026.** `IJCKG_WP/main.tex` had said **95 repositories** in all nine places; **all nine are now corrected to 96.** Corroborating evidence that 96 was always the true value: the same paper states "The other 70 cannot even be built" — and 96 − 26 = 70, not 95 − 26 = 69. The 95 was a transcription error, not a different corpus definition.
  - Legitimate uses of **95** that should stay: "95 with retrievable papers", the silver evaluation set (n=95), and the Zenodo record's title ("…corpus of 95 machine-learning papers with GitHub repositories"). SRAF's `main.tex` uses 95 in exactly these three places and is correct as-is.
- **Failure taxonomy (26 repos):** 18 documentation/artifact gaps, 4 metric-not-reproducible-by-construction, 4 our-environment. Plus a named mode **"environment rot"** (deprecated dependency), exemplified by a positive control.
- **Positive-control ablation:** autonomous extraction **0/3**, gold recipes **2/3** (CIFAR-10 94.25 vs claimed 94.37; SST-2 93.23 vs 92.70; 3rd = env rot, `pytorch_lightning.metrics` removed). → *execution works; extraction is the bottleneck.*
- **Recipe quality (17):** ⟳ **re-verified against `data/recipes/*.json` — all figures confirmed exactly.** 13 have a command, but only **6 concrete** (7 placeholders, 4 none). Confidence **8 high / 9 low**, and it's well-calibrated: all 6 concrete are high-confidence; all 9 low-confidence are non-runnable.
  - Concrete + high: study006, 009, 014, 020, 021, 024. Placeholder: 003, 008, 012, 018, 019, 025, 026 (018 is the one high-confidence placeholder). Empty: 002, 007, 010, 011.
- **From SRAF main paper:** ~55.8% resolve (48/86), 52.3% build (45/86); **software license is the top predictor** (OR≈7.3 resolve / 7.7 build, p≈0.03); aggregate FAIR-R score does *not* predict reproduction (ρ=+0.155 resolve, ρ=+0.099 build, n.s.); extraction F1≈0.27; calibration exemplar 87.3 vs typical 47.3.
  - ⟳ **All of the above re-derived from the raw result JSONs on 9 Sept 2026 and confirmed unchanged.** The regressions are computed over the 86 build-attempted repos, so they were never affected by the corpus-count bug below.
  - ⟳ **NEW RESULT worth using:** per-dimension Spearman shows the **Reusable** FAIR-R dimension *does* correlate with outcome (ρ=+0.244, p=0.024\* resolve; ρ=+0.209, p=0.053 build), while Findable/Interoperable/Reproducible are flat. This sharpens the RQ4 story: the *aggregate* score is uninformative but one sub-dimension carries signal — and it is the dimension containing licensing, consistent with license being the top single predictor. Table is in `analysis/predictor_analysis.md`.
- ⟳ **FAIR-R distribution (corrected):** mean **49.4**, median 51.8, min 26.6, max 56.3; tiers **61 fair / 35 poor**. The previously checked-in summary reported mean 29.3 with all 96 repos "poor" — that file was stale, not the data. The `47.3` "typical" figure quoted in the papers is consistent with the corrected distribution.

## ⟳ Data-integrity fix applied 9 Sept 2026 (read this before trusting any older analysis output)

Two checked-in analysis outputs in `rdip-sraf-repro/analysis/` were wrong. Both are now fixed; changes are **uncommitted** in the working tree.

**Bug:** `summarize_results.py` and `predictor_analysis.py` both globbed `validation/results/*.json` indiscriminately. That directory also holds non-corpus artefacts:
- `study001_vs_study002.json` — a WS2 semantic-diff / conflict-graph output, no `study_id`
- `ref005.json` — a reference probe (`status: clone_failed`)

The diff file was counted as a 97th repository, producing a phantom all-empty row. This is the origin of the **96-vs-97 discrepancy**: `results_summary.md` claimed "97 repos processed", "Build attempted: 86/97", "license detected 81/97 (83.5%)", "commit hash 96/97 (99.0%)", "repos with NO env files: 1/97". The last two were qualitatively wrong — the phantom row *was* the repo with "no env files" and the one "missing" a commit hash.

**Fix:** both scripts now require `study_id` to match `^study\d{3}$` and skip everything else, logging what it skipped.

**What changed after regeneration:**
- Corpus count 97 → **96** everywhere; `86/96`, `81/96 (84.4%)`, `96/96 (100.0%)` commit hashes, `0/96 (0.0%)` repos with no env files.
- FAIR-R block corrected as above (the old checked-in CSV had a stale, obviously-broken narrow band of ~26–34 for all 96 rows; the raw JSONs always had the right values).
- `predictor_analysis.md` header 97 → 96; **every regression coefficient, odds ratio and p-value unchanged**; gained the per-dimension Spearman table (the checked-in copy predated that section).

**Bottom line: no published or accepted number is affected.** The headline percentages divide by 86 (build-attempted), and the predictor analysis always read the raw JSONs. Only the two derived summary files in `analysis/` were misleading.

## The new ontology term

`rdip:ExecutionRecipe` (proposed extension). Fields: `runCommand`, `setupStep`, `requiresDataset`, `requiresCheckpoint`, `producesMetric`, `entryPoint`, `recipeConfidence`. (⟳ Note: the serialised JSON in `data/recipes/` uses snake_case — `run_command`, `setup_steps`, `requires_dataset`, `requires_checkpoint`, `produces_metric`, `entry_point`, `confidence`, plus `study_id` and `repo_url`.) Extraction model: open-weight **Mistral-Small-24B** served locally (vLLM). Two-phase because a 24B model + an experiment can't share one 48 GB GPU.

## Where the code artifacts live (in `rdip-sraf-repro/`)

- FAIR-R SHACL shapes: `sre_engine/shacl/*.ttl`
- Extraction prompts: `rag_pipeline/extractor.py`, `rag_pipeline/recipe_extractor.py`
- Result-level reproduction: `result_repro/` (two-phase `extract_recipes.py` + `run_all.py`, `summarize.py`, `manifest.yaml` (26 studies: 9 skipped, 17 pending), `validation_manifest.yaml`, `gold_recipes/`)
- Extracted recipes: `data/recipes/` (20 files = 17 studies + 3 controls); ground truth: `data/ground_truth/`
- ⟳ Corpus audit results: `validation/results/study001–096.json` — **the source of truth** for corpus statistics. Derived: `analysis/results_summary.{md,csv}`, `analysis/predictor_analysis.md`, `analysis/predictor_table.csv`.
- ⟳ Multi-model extraction evaluation: `results_gold.json` / `results_silver.json` (Qwen2.5-14B-int8, Llama-3.1-8B-w8a8, Mistral-Small-24B-w8a8), `evaluation/compare_models.py`. This is the scaffolding WS3 should extend to paid models.
- Corpus (95 papers/96 repos) on Zenodo: `doi:10.5281/zenodo.19919042`

Run result-level reproduction (Slurm, GPU): `sbatch result_repro/extract_recipes.sbatch` (Phase 1) → `sbatch result_repro/run_all.sbatch` (Phase 2) → `python -m result_repro.summarize`. Positive controls: add `--export=ALL,MANIFEST=result_repro/validation_manifest.yaml`.

## Open TODOs ⟳ (as of 9 Sept 2026)

**Workshop paper (`IJCKG_WP/main.tex`) — before submit:**
1. `\conference{}` currently reads `IJCKG 2026: International Joint Conference on Knowledge Graphs, 2026`. CEUR-ART expects the **workshop's** name and dates, not the host conference. Still needs the exact workshop title + dates. **This is the last substantive blocker.**
2. Confirm `github.com/open-rdip/rdip-sraf-repro` is **public** (could not be verified from the sandbox — proxy blocks GitHub). A paper-cited URL that 404s for reviewers is the worst possible failure mode for a reproducibility paper.
3. **Recompile on Overleaf and re-check the page count.** ⟳ `main.bbl` in the folder is currently 0 bytes (see note below); Overleaf regenerates it because `main.tex` uses `\bibliography{references}` at L320. Was 11 pages before the edit; the 95→96 change is single-character and will not move it.
4. Consider adding SRAF's precision parenthetical to §4.3 — "96 repositories … (95 with retrievable papers)" — so the two papers read identically on corpus definition. Not required; the count itself now matches.
5. Housekeeping in the folder: `.DS_Store` and the stale `sample-1col.*` build artifacts are sitting next to `main.tex`.

*Resolved 9 Sept 2026:* **all nine 95→96 corrections applied**; released-code `\url{}` no longer ends in `.git`. *Resolved earlier:* repo URL placeholder (now real), `\conference{}` populated (but see #1), GenAI declaration written, page count fine at **11 pages** (limit 10–16). Acknowledgments block still absent — optional.

⟳ **Note on local LaTeX builds — do not repeat this.** Attempting `pdflatex` on the Mac fails: `ccicons.sty`, the Libertinus fonts and `elsarticle-num-names.bst` are all absent locally and are **not fetchable** (no network from the sandbox shell, and CTAN is blocked from the cloud container). A failed run **empties `main.bbl` and overwrites `main.log`/`main.pdf`**. This happened on 9 Sept 2026; `main.pdf` was restored from backup, but `main.bbl` is now 0 bytes and can only be regenerated where the style file exists. **Compile the CEUR paper on Overleaf only.**

**Build note:** CEUR needs Libertinus fonts + `ccicons` + `elsarticle-num-names.bst` (present on Overleaf; the sandbox used stubs + lmodern fallback — do **not** commit an `\usepackage{lmodern}` line). LaTeX: `pdflatex → bibtex → pdflatex → pdflatex`.

**SRAF camera-ready (`SRAF/main.tex`):** ⟳ **DONE — closed out and verified 9 Sept 2026.** Says 96 in all ten places; the three `95`s are the legitimate ones listed above; no `TODO-REPLACE` remains; repo URL is real. Only nit (cosmetic, and it is already submitted, so leave it): its `\url{}` also carries the `.git` suffix. One tiny discrepancy for the record: the paper reports FAIR-R "mean 49.6, standard deviation 5.1" while the current raw results give mean 49.41, sd 5.23 — a ~0.2 drift, immaterial and not worth touching a camera-ready over, but worth using the recomputed figures in the journal paper. (Repo URL placeholder and LICENSE both resolved; R1's "bulletize sources after Fig 2" was deferred for space; three large tables at `\scriptsize` to hold 15 pages.)

**Repo:** ⟳ **Cleanup and LICENSE are DONE.** Working tree was clean before this session's analysis fix; no `__pycache__`, `.pyc`, `.DS_Store`, `.bak` or `.pytest_cache` anywhere, and none tracked. Remaining: **commit the `analysis/` fix** described above (6 files).

**Research directions (from Prof. Fujiwara, NII):**
- **Cost/incentive design:** "who pays for reproducibility verification?" is unsolved — a practical answer (incl. *selective* verification by criteria) could anchor the PhD. ⟳ The new Reusable-dimension result is a concrete hook here: it suggests cheap, targeted signals (licence/reuse metadata) beat an expensive aggregate score for triage.
- **Metadata distribution:** get RDIP/SRAF reproducibility metadata into research-metadata platforms (NII RDM, likely CiNii Research) so it's findable — collaborate with **Minamiyama**.
- Look into the **RDA Reproducibility Working Group** (he's a member; link he shared).
- **Survey existing reproducibility-assisting services** (publisher/venue reproduction platforms); position the gap.
- **Try SOTA LLMs (Claude/GPT)** as the recipe extractor vs the open-weight model (WS3 / workshop future work). ⟳ Extend `evaluation/compare_models.py` + `results_gold.json`/`results_silver.json`, which already compare three open-weight models.
- Stay in **ML** reproducibility (don't move to psychology/biology).
- Await his email with NII's Jupyter-notebook reproduction system URL; **forward the presentation slides** to Fujiwara + Minamiyama.

**Remaining research workstreams:** WS2 semantic-diff evaluation (RQ2, engine built — output format visible in `validation/results/study001_vs_study002.json`), WS3 paid-model extraction comparison.

## Presentation

- Content: `SRAF/Overview_Presentation_slides_content.md` (17-slide overview + references + citations-by-slide).
- A 22-slide deck was built (`RDIP Overview.pdf`). Review flagged: unify **95 vs 96** (see TODO #1 — now a paper-level decision, not just a slide fix); the title reuses "RDIP" as *platform* while slide 4 uses it as the *ontology* — a naming collision to resolve; slide 8 FAIR-R table overflows below the footer; several typos ("Surverys", "acutally", "reporduced", "RDS"→"RDA").
- ⟳ If the corrected FAIR-R distribution (mean 49.4, 61 fair / 35 poor) appears on any slide sourced from the old `results_summary.md`, it needs updating — the old file said all 96 were "poor".

## Figures (reusable)

`rdip_ontology_focused.pdf/.svg` (RDIP + ExecutionRecipe), `execrecipe_focus.pdf/.dot` (the class + properties), `experiment_flow.pdf/.dot` (two-phase pipeline), `sraf_architecture_focused.pdf`, `fairr_dist.pdf` (⟳ regenerate if it was plotted from the stale summary).

## Working notes / gotchas

- **CEUR is the source of truth** for the workshop paper; the LNCS `IJCKG Workshop Paper/` copy is stale.
- Keep numbers consistent with the tables above.
- Corpus PDFs and cloned repos are gitignored (large); only ground truth / extractions / recipes are tracked.
- ⟳ **`validation/results/` is not homogeneous.** It mixes per-study audit results with semantic-diff outputs and reference probes. Any new script that reads it must filter on `study_id` matching `^study\d{3}$`, or it will repeat the 97-repo bug.
- ⟳ **Derived files in `analysis/` can go stale.** They are checked in but not regenerated automatically. Regenerate (`python3 analysis/summarize_results.py && python3 analysis/predictor_analysis.py`) before quoting any number from them, and prefer `validation/results/*.json` as the source of truth. `predictor_analysis.py` needs `statsmodels`.
