# Gold execution recipes

Human-verified reference recipes, used **only** to score the engine's recipe
extraction (`eval_recipes.py`). The run harness never reads these — it executes the
engine-`extracted` recipe in `data/recipes/<study>.json`. This mirrors the RQ3
gold/silver setup: gold measures how well the system derives "how to reproduce" on
its own.

Annotate from the repo's README (the command that produces the paper's headline
metric). Only fill the studies you actually verify — a small, correct gold set is
enough. File name = `<study_id>.json`, same schema as an extracted recipe:

```json
{
  "study_id": "study002",
  "run_command": "python main.py --model Keci --path_dataset_folder KGs/UMLS --num_epochs 100 --eval_model test",
  "entry_point": "main.py",
  "setup_steps": ["pip install -e ."],
  "requires_dataset": [{"name": "UMLS", "download": "ships in repo (KGs/UMLS)"}],
  "requires_checkpoint": null,
  "produces_metric": [{"metric": "MRR", "dataset": "UMLS"}],
  "confidence": "high"
}
```

Copy `study002.template.json` to `study002.json` and edit.
