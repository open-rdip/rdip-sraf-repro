# Gold-standard annotation schema (RQ3)

The gold standard is a set of hand-annotated JSON files, one per study, that
record the reproducibility metadata a careful human finds **in the paper PDF**.
`eval_extraction.py` compares each model's automatic extraction against these to
report precision / recall / F1.

## File location & naming

    evaluation/gold_standard/<study_id>.json      e.g. study001.json

One file per annotated study. Annotate **50** studies (we start from the 12-paper
pilot and grow to 50). Files ending in `.template.json` are ignored by the
evaluator.

## Format

Each file mirrors the pipeline's extraction `metadata` block, so gold and
prediction are directly comparable. Either wrap it in `{"metadata": {…}}` or
provide the fields flat — the evaluator accepts both.

```json
{
  "study_id": "study001",
  "annotator": "initials",
  "metadata": {
    "dependencies":       [{"name": "pytorch", "version": "1.13.1"}],
    "random_seeds":       [42, 1234],
    "hardware":           {"gpu_model": "NVIDIA A100",
                           "cuda_version": "11.7", "cpu_info": null},
    "hyperparameters":    [{"name": "learning_rate", "value": "3e-4"},
                           {"name": "batch_size", "value": "32"}],
    "datasets":           [{"name": "ImageNet", "version": null}],
    "methods":            [{"name": "ResNet-50", "description": "backbone"}],
    "evaluation_results": [{"metric": "accuracy", "value": "0.943",
                            "split": "test"}]
  }
}
```

## Annotation rules (keep gold and model judged on the same basis)

- Record only what is **stated in the paper text** (the PDF the model also sees),
  not what is in the repo — this evaluates *paper* extraction.
- `random_seeds`: integers explicitly given as seeds. Omit if none stated.
- `dependencies`: libraries/frameworks with the version if the paper gives one;
  leave `version` as `null` when unversioned.
- `hyperparameters`: name + value as written (`"3e-4"`, `"32"`); don't convert.
- `datasets`: dataset name; `version` only if stated.
- `evaluation_results`: each headline reported metric with its value and the
  split it was measured on (`train`/`validation`/`test`/`null`). Record the
  paper's **claimed** number — this is also what RQ (result reproducibility, #20)
  compares re-run numbers against.
- `hardware`: GPU model, CUDA version, CPU if stated; `null` otherwise.
- Use `[]` for an absent list, `null` for an absent scalar.

## How scoring works

- **lenient** match: an item counts as found if its identifying key matches —
  dependency NAME, hyperparameter NAME, dataset NAME, method NAME, eval
  (metric, split). Measures whether the model found the right *thing*.
- **strict** match: key **plus value** (dependency name+version, hyperparam
  name+value, eval metric+value+split). Measures whether it also got the value
  right. Values are canonicalised so `0.94`, `0.940`, and `94%` compare equal.
- Reported per field and overall as micro-averaged P/R/F1 (pool TP/FP/FN across
  studies) plus a macro F1 (mean of per-study F1).

Run, once extractions exist:

    python evaluation/eval_extraction.py --model <model_slug>          # lenient
    python evaluation/eval_extraction.py --model <model_slug> --strict # +values
