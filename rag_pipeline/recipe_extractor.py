"""LLM extraction of the *execution recipe* — how to reproduce a study's headline
result — as first-class RDIP metadata.

The command that reproduces a paper's number lives in the artifacts (the README's
Usage/Evaluation section, a run.sh / reproduce.sh / Makefile, and the paper's
"reproducing results" text), not just the paper body. So the recipe extractor reads
the repository documentation (+ an optional paper passage) and emits a structured
recipe. This makes result-level reproduction *engine-driven*: for a new paper the
same extraction runs, with no hand-written command.

    from rag_pipeline.recipe_extractor import read_repo_text, extract_recipe
    recipe = extract_recipe(read_repo_text("/path/to/cloned/repo"),
                            backend="vllm", model="...")

The recipe schema (also what map_recipe expects):
    run_command          : the single shell command producing the headline metric
    setup_steps          : ordered prep commands (install / data / checkpoint download)
    requires_dataset     : [{name, download}]
    requires_checkpoint  : URL/path of a needed pretrained checkpoint, or null
    produces_metric      : [{metric, dataset}]  — what the command reports
    entry_point          : the script the command invokes
    confidence           : high | medium | low
"""
from __future__ import annotations

import glob
import os

from rag_pipeline.extractor import get_extractor, _parse_json

RECIPE_SYSTEM_PROMPT = (
    "You are a software-reproducibility assistant. Given the documentation of a "
    "research code repository, you identify exactly how to re-run the experiment "
    "that produces the paper's HEADLINE reported metric, and return it as JSON."
)

RECIPE_PROMPT = """From the repository documentation below, extract the execution
recipe needed to reproduce the paper's main reported result. Return ONLY this JSON:
{{
  "run_command": "the single shell command that runs the evaluation producing the headline metric, or null",
  "setup_steps": ["ordered shell commands to prepare env/data/checkpoint before run_command"],
  "requires_dataset": [{{"name": "string", "download": "URL or command or null"}}],
  "requires_checkpoint": "URL/path of a pretrained checkpoint needed, or null",
  "produces_metric": [{{"metric": "string", "dataset": "string or null"}}],
  "entry_point": "the script/file the run_command invokes, or null",
  "confidence": "high | medium | low"
}}
Rules:
- Prefer an evaluation/test command over full training when the paper reports a metric from a released checkpoint.
- Use commands exactly as written in the docs; do NOT invent flags or file names.
- Do NOT include a command to clone this repository — it is already cloned and you are running inside it.
- If a checkpoint or dataset is only given as a URL, put the download AND any unzip/extract into setup_steps (e.g. "wget <url> -O ckpt.zip", "unzip ckpt.zip -d ckpt"), and make run_command reference the resulting LOCAL path. Never pass a URL where a local file/directory path is expected.
- If the run command has a placeholder path (e.g. /path/to/ckpt, $checkpoint_dir), it is not directly runnable: keep it but set confidence to "low".
- When the repo is a multi-method toolbox, choose the config/checkpoint that matches THIS paper's method and reported result, not a generic demo config.
- If the docs do not state how to reproduce a reported number, set run_command to null and confidence to "low".
- setup_steps are only commands explicitly documented (install, data download, checkpoint download).

Repository documentation:
{repo_text}"""

# Doc files searched, in priority order.
REPO_DOC_FILES = (
    "README.md", "README.rst", "README.txt", "README", "readme.md",
    "reproduce.sh", "run.sh", "eval.sh", "test.sh", "Makefile", "makefile",
    "REPRODUCE.md", "EVALUATION.md", "docs/reproduce.md", "docs/getting_started.md",
)

RECIPE_KEYS = ("run_command", "setup_steps", "requires_dataset",
               "requires_checkpoint", "produces_metric", "entry_point", "confidence")


def read_repo_text(repo_dir: str, max_chars: int = 16000) -> str:
    """Concatenate the repo's documentation/run scripts into one passage."""
    parts, seen = [], set()
    for rel in REPO_DOC_FILES:
        p = os.path.join(repo_dir, rel)
        if os.path.isfile(p) and p not in seen:
            seen.add(p)
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            parts.append(f"===== {rel} =====\n{txt}")
    # any remaining top-level shell scripts (train/eval helpers)
    for p in sorted(glob.glob(os.path.join(repo_dir, "*.sh"))):
        if p in seen:
            continue
        parts.append(f"===== {os.path.basename(p)} =====\n"
                     + open(p, encoding="utf-8", errors="ignore").read())
    return "\n\n".join(parts)[:max_chars]


def _normalise(r: dict) -> dict:
    """Coerce the model output to the stable recipe schema."""
    out = {"run_command": None, "setup_steps": [], "requires_dataset": [],
           "requires_checkpoint": None, "produces_metric": [], "entry_point": None,
           "confidence": "low"}
    if isinstance(r, dict):
        for k in RECIPE_KEYS:
            if r.get(k) is not None:
                out[k] = r[k]
    for k in ("setup_steps", "requires_dataset", "produces_metric"):
        if not isinstance(out[k], list):
            out[k] = [out[k]] if out[k] else []
    # normalise a nullish command string to None
    if isinstance(out["run_command"], str) and \
            out["run_command"].strip().lower() in ("", "null", "none", "n/a"):
        out["run_command"] = None
    return out


METRIC_SYSTEM_PROMPT = (
    "You read machine-learning experiment logs and report the obtained numeric "
    "result for the requested metrics, as JSON."
)

METRIC_PROMPT = """An experiment was run to reproduce these claimed metrics:
{claimed}

From the experiment log below, report the OBTAINED value for each metric that
appears. Return ONLY:
{{"obtained": [{{"metric": "string", "value": "string", "split": "string or null"}}]}}
Omit any metric whose value is not present in the log. Do not invent numbers.

Log (tail):
{log}"""


def parse_metrics_from_log(log: str, claimed: list, backend: str | None = None,
                           model: str | None = None) -> list:
    """Use the LLM to read the obtained metric values out of an experiment log."""
    claimed_str = "; ".join(
        f"{c.get('metric')} (claimed {c.get('claimed')}, split {c.get('split')})"
        for c in (claimed or [])) or "any reported metric"
    ex = get_extractor(backend, model)
    try:
        raw = ex._complete(METRIC_SYSTEM_PROMPT,
                           METRIC_PROMPT.format(claimed=claimed_str, log=log[-6000:]))
        d = _parse_json(raw)
        got = d.get("obtained", []) if isinstance(d, dict) else []
        return [g for g in got if isinstance(g, dict) and g.get("value") not in (None, "")]
    except Exception as e:  # noqa: BLE001
        print(f"[metric-parse:{ex.name}] error: {e}")
        return []


def extract_recipe(repo_text: str, paper_text: str | None = None,
                   backend: str | None = None, model: str | None = None) -> dict:
    """Extract the execution recipe from repo documentation (+ optional paper text)."""
    if paper_text:
        repo_text = (repo_text
                     + "\n\n===== paper: reproducing results =====\n"
                     + paper_text[:4000])
    ex = get_extractor(backend, model)
    try:
        raw = ex._complete(RECIPE_SYSTEM_PROMPT, RECIPE_PROMPT.format(repo_text=repo_text))
        return _normalise(_parse_json(raw))
    except Exception as e:  # noqa: BLE001
        print(f"[recipe:{ex.name}] error: {e}")
        return _normalise({})
