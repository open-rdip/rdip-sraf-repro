# RDIP-SRAF — Reproducibility Auditing and Result-Level Reproduction for ML Research

Software artifact behind three papers:

- **RDIP ontology** — *Enabling FAIR Research Lifecycle Provenance: The RDIP Project-Centric Integration Profile* (TPDL 2026).
- **SRAF** — *SRAF: An Ontology-Grounded Knowledge Graph Framework for Auditing the Reproducibility of Machine-Learning Research* (IJCKG 2026, main track).
- **Result-level reproduction** — *From Builds to Numbers: Engine-Driven Result-Level Reproduction of Machine-Learning Papers and a Taxonomy of Failure* (IJCKG 2026, workshop).

The pipeline does three things in order: **describe** a study as an RDIP knowledge graph, **measure** its reproducibility with the graded FAIR-R score, and **test** whether it actually reproduces by re-running the code.

## Where to find the key artifacts

| Artifact | Location |
|---|---|
| RDIP ontology (Turtle) | `.ontology_cache/rdip.ttl` (canonical namespace: `w3id.org/rdip/`) |
| FAIR-R SHACL shapes (the scoring rules) | `sre_engine/shacl/*.ttl` |
| LLM extraction prompts (paper → RDIP) | `rag_pipeline/extractor.py` |
| Execution-recipe extraction (`rdip:ExecutionRecipe`) + its prompt | `rag_pipeline/recipe_extractor.py` |
| Result-level reproduction pipeline | `result_repro/` |
| Study manifest (26 buildable repos) | `result_repro/manifest.yaml` |
| Positive-control set + gold recipes | `result_repro/validation_manifest.yaml`, `result_repro/gold_recipes/` |
| Human-verified ground truth | `data/ground_truth/` |
| Corpus (95 papers / 96 repositories) | Zenodo: `doi:10.5281/zenodo.19919042` |

## Repository layout

- `rag_pipeline/` — retrieval-augmented LLM extraction from papers into RDIP metadata, including the execution-recipe extractor and its prompts.
- `lifter/` — deterministic repository parsing and per-study graph construction (dependencies, license, environment, identifiers; Zenodo/DataCite lift).
- `sre_engine/` — the scoring engine: the FAIR-R rubric and its SHACL shapes (`sre_engine/shacl/`), plus the semantic-diff engine.
- `build_harness/` — version-aware environment reconstruction (the "does it build" tier).
- `result_repro/` — engine-driven result-level reproduction: two-phase pipeline (`extract_recipes.py`, `run_all.py`), comparison, failure classifier, taxonomy (`summarize.py`), manifest, and gold recipes.
- `calibration/` — FAIR-R calibration against reference artifacts.
- `evaluation/` — extraction-accuracy evaluation (entity-level F1 vs. gold/silver ground truth).
- `analysis/` — statistical analysis (e.g., logistic regression of the reproduction outcome on metadata predictors).
- `dashboard/` — Streamlit dashboard for viewing a study's graph and FAIR-R score.
- `triplestore/` — RDF store (Oxigraph) client and data.
- `data/` — ground truth, extractions, and extracted recipes (`data/recipes/`). Paper PDFs are not committed; see the corpus DOI above.
- `scripts/`, `cluster/`, `containers/`, `tests/`, `docs/` — utilities, cluster/Slurm configs, container files, tests, and documentation.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in endpoints / keys as needed
```

## Running

**FAIR-R scoring (SRAF).** Lift a study into an RDIP graph (`lifter/`, `rag_pipeline/`) and score it with the SHACL shapes in `sre_engine/`. See `scripts/` for helper entry points (e.g., dumping the per-criterion FAIR-R score for a study).

**Result-level reproduction (two phases, GPU cluster).** Phase 1 serves the extraction model and writes each study's execution recipe; Phase 2 runs and compares with no model loaded (they cannot share one GPU):

```bash
# Phase 1 — extract execution recipes (LLM served on the GPU)
sbatch result_repro/extract_recipes.sbatch
# Phase 2 — rebuild, run, compare, classify (streaming; deletes artifacts as it goes)
sbatch result_repro/run_all.sbatch
# Aggregate into the funnel + failure taxonomy
python -m result_repro.summarize          # writes result_repro/results/report.md
```

Run the positive controls by pointing the same jobs at the validation manifest:
`--export=ALL,MANIFEST=result_repro/validation_manifest.yaml`.

## Data & corpus

The corpus of 95 ML papers / 96 repositories, the per-study RDIP graphs, and the human-verified ground truth are archived on Zenodo (`doi:10.5281/zenodo.19919042`). Paper PDFs and cloned repositories are not committed here (see `.gitignore`).

## License

SRAF: [MIT License](https://opensource.org/licenses/MIT)
Code: [MIT License](https://opensource.org/licenses/MIT)
