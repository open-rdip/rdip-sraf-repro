"""Deterministic extraction of *experimental* facts from a repository.

Why this exists
---------------
SRAF describes a repository's ENVIRONMENT deterministically (pip/conda/docker
parsers -> dependencies, versions, digests) but its EXPERIMENT only through an
LLM, at entity-level F1 ~= 0.27. That asymmetry is what makes the paper-vs-repo
semantic diff impossible today: the paper side has datasets, hyperparameters and
metrics; the repository side has none of them.

This module closes the gap. It reads configs, argparse definitions and
documentation and returns the same fact kinds the extractor produces, so the two
can be compared:

    datasets          [{name, canonical, evidence}]
    hyperparameters   [{name, canonical, value, evidence}]
    metrics           [{name, canonical, evidence}]
    seeds             [{value, evidence}]

Design constraints, deliberate and load-bearing:

* **No language model.** The diff's contribution is that it yields real
  precision and recall against injected ground truth. An LLM anywhere in this
  path would reintroduce the extraction confound the diff exists to escape.
* **Evidence-bearing.** Every fact carries the file and line that produced it,
  so any conflict the diff reports can be traced to its source by a reader.
* **Bounded.** File-count and byte caps, so one enormous repository cannot stall
  a corpus sweep.
* **Frozen vocabularies.** ALIASES and metric tables are tuned on this corpus and
  must be frozen before the final sweep, then reported in full — the same
  discipline applied to the Tier-B rules (see docs/paper_notes.md section M).

Usage:
    python3 build_harness/repo_facts.py <repo_dir> [--json out.json]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import warnings
from collections import OrderedDict
from pathlib import Path

# Bump when extraction logic changes; consumers re-run on mismatch.
FACTS_VERSION = 8

MAX_FILES = 400
MAX_BYTES = 300_000
CONFIG_SUFFIXES = (".yaml", ".yml", ".json", ".py", ".cfg", ".ini", ".toml")
CONFIG_DIR_HINTS = ("config", "configs", "conf", "experiments", "options", "opts")
SKIP_PARTS = {".git", "node_modules", "site-packages", "third_party", "build",
              "dist", ".eggs", "__pycache__", ".github"}

# ── Canonical vocabularies (FROZEN before the final sweep) ───────────────────
# Maps many surface forms onto one canonical name so "CIFAR-100", "cifar100"
# and "CIFAR_100" align. Order matters: longer keys are matched first.
DATASET_ALIASES = {
    "cifar100": "CIFAR-100", "cifar-100": "CIFAR-100", "cifar_100": "CIFAR-100",
    "cifar10": "CIFAR-10", "cifar-10": "CIFAR-10", "cifar_10": "CIFAR-10",
    "imagenet1k": "ImageNet", "imagenet-1k": "ImageNet", "ilsvrc": "ImageNet",
    "imagenet": "ImageNet",
    "mscoco": "COCO", "ms-coco": "COCO", "cocodataset": "COCO", "coco": "COCO",
    "cityscapes": "Cityscapes", "ade20k": "ADE20K", "ade": "ADE20K",
    "pascalvoc": "PASCAL VOC", "pascal-voc": "PASCAL VOC", "voc2012": "PASCAL VOC",
    "voc2007": "PASCAL VOC", "voc": "PASCAL VOC",
    "kitti": "KITTI", "scannet": "ScanNet", "sunrgbd": "SUN RGB-D",
    "nuscenes": "nuScenes", "waymo": "Waymo",
    "mnist": "MNIST", "fashionmnist": "Fashion-MNIST",
    "sst2": "SST-2", "sst-2": "SST-2", "glue": "GLUE", "squad": "SQuAD",
    "wikitext": "WikiText", "c4": "C4", "openwebtext": "OpenWebText",
    "visualgenome": "Visual Genome", "vg": "Visual Genome",
    "librispeech": "LibriSpeech", "celeba": "CelebA", "lsun": "LSUN",
    "oasis": "OASIS", "ixi": "IXI", "chestxray14": "ChestX-ray14",
}
METRIC_ALIASES = {
    "top-1": "Top-1 accuracy", "top1": "Top-1 accuracy",
    "top-5": "Top-5 accuracy", "top5": "Top-5 accuracy",
    "accuracy": "Accuracy", "acc": "Accuracy", "err": "Error rate",
    "map": "mAP", "mean average precision": "mAP", "ap": "AP",
    "miou": "mIoU", "mean iou": "mIoU", "iou": "IoU",
    "pq": "PQ", "panoptic quality": "PQ",
    "f1": "F1", "f-1": "F1", "precision": "Precision", "recall": "Recall",
    "bleu": "BLEU", "rouge": "ROUGE", "meteor": "METEOR",
    "ppl": "Perplexity", "perplexity": "Perplexity",
    "psnr": "PSNR", "ssim": "SSIM", "fid": "FID", "is": "Inception Score",
    "dsc": "Dice", "dice": "Dice", "mrr": "MRR", "ndcg": "NDCG",
    "wer": "WER", "cer": "CER", "auc": "AUC", "auroc": "AUROC",
    "mse": "MSE", "mae": "MAE", "rmse": "RMSE",
    # mm-detection / mm-segmentation surface forms: `--eval bbox` and
    # `metric=['bbox','segm']` are how that family names box and mask AP.
    "bbox": "mAP", "segm": "Mask AP", "proposal": "AR",
    "mdice": "mDice", "macc": "mAcc", "aacc": "aAcc",
    "pq": "PQ", "sq": "SQ", "rq": "RQ",
}
# Hyperparameter surface forms -> canonical
HP_ALIASES = {
    "lr": "learning_rate", "learning_rate": "learning_rate",
    "base_lr": "learning_rate", "init_lr": "learning_rate",
    "bs": "batch_size", "batch_size": "batch_size",
    "batch": "batch_size", "samples_per_gpu": "batch_size",
    "epochs": "epochs", "num_epochs": "epochs", "max_epochs": "epochs",
    "total_epochs": "epochs", "n_epochs": "epochs",
    "iters": "iterations", "max_iters": "iterations", "num_iters": "iterations",
    "weight_decay": "weight_decay", "wd": "weight_decay",
    "momentum": "momentum", "optimizer": "optimizer", "optim": "optimizer",
    "dropout": "dropout", "warmup": "warmup", "warmup_iters": "warmup",
    "image_size": "image_size", "img_size": "image_size", "crop_size": "image_size",
    "num_classes": "num_classes", "temperature": "temperature",
}

_DATASET_RE = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(sorted(map(re.escape, DATASET_ALIASES), key=len, reverse=True))
    + r")(?:(?![A-Za-z0-9])|(?-i:(?=[A-Z][a-z])))", re.I)
# ── Metrics a repository can actually COMPUTE ────────────────────────────────
#
# The `metric_never_computed` conflict asks whether the code can produce the
# metric the paper claims, so a keyword sweep is not enough: "accuracy" appears
# in prose everywhere. Each signal below is structurally anchored, and each
# detected metric records WHICH signal found it, so precision can be reported
# per signal class rather than as one undifferentiated number.
#
# Strength order (a stronger signal for the same metric wins):
#   metric_api  — a metrics library function or class is called
#   eval_config — an evaluator/metric is declared in a config
#   cli_flag    — a documented --eval/--metric flag
#   logged      — the name is written to a results dict or logging sink

METRIC_SIGNAL_RANK = {"metric_api": 3, "eval_config": 2, "cli_flag": 1, "logged": 0}

# Callable name -> canonical metric. Direct mapping, not the alias table: these
# are unambiguous API names, so no boundary heuristics are needed.
METRIC_API = {
    # scikit-learn
    "accuracy_score": "Accuracy", "balanced_accuracy_score": "Accuracy",
    "f1_score": "F1", "precision_score": "Precision", "recall_score": "Recall",
    "roc_auc_score": "AUROC", "average_precision_score": "AP",
    "mean_squared_error": "MSE", "mean_absolute_error": "MAE",
    "jaccard_score": "IoU", "matthews_corrcoef": "MCC",
    # torchmetrics
    "MeanAveragePrecision": "mAP", "JaccardIndex": "IoU", "F1Score": "F1",
    "PeakSignalNoiseRatio": "PSNR",
    "StructuralSimilarityIndexMeasure": "SSIM",
    "FrechetInceptionDistance": "FID", "Perplexity": "Perplexity",
    "WordErrorRate": "WER", "CharErrorRate": "CER",
    "RetrievalNormalizedDCG": "NDCG", "RetrievalMRR": "MRR",
    "Dice": "Dice",
    # detection / segmentation evaluators
    "COCOeval": "mAP", "CocoMetric": "mAP", "IoUMetric": "mIoU",
    "CityscapesMetric": "mIoU", "PanopticMetric": "PQ", "COCOPanopticMetric": "PQ",
    # text generation
    "corpus_bleu": "BLEU", "sentence_bleu": "BLEU", "BLEU": "BLEU",
    "rouge_scorer": "ROUGE", "meteor_score": "METEOR",
}

_METRIC_API_RE = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, METRIC_API), key=len, reverse=True))
    + r")(?![A-Za-z0-9_])")

# evaluate.load("accuracy") / load_metric("glue", "sst2")
_METRIC_LOAD_RE = re.compile(
    r"(?:evaluate\.load|load_metric)\s*\(\s*['\"]([A-Za-z0-9_\-]+)['\"]")

# metric='mIoU'  ·  metrics=['bbox','segm']  ·  eval_metric: accuracy
# Captures the whole right-hand side so a list yields every element; a single
# quoted value is just a list of one. Matching only the first quoted item lost
# `segm` from `metric=['bbox','segm']`, which is the common detection setting.
_METRIC_CFG_RE = re.compile(
    r"(?:\beval_metric|\bkey_metric|\bmetrics?)\s*[:=]\s*(\[[^\]\n]*\]|['\"][A-Za-z0-9_\-]+['\"])",
    re.I)
_QUOTED_RE = re.compile(r"['\"]([A-Za-z0-9_\-]+)['\"]")

# results["mIoU"]  ·  scores['f1']  ·  log_dict["val/acc"]
_METRIC_LOOKUP_RE = re.compile(
    r"(?:results?|scores?|metrics?|log_?dict|eval_results?|outputs?)"
    r"\s*\[\s*['\"]([A-Za-z0-9_/\-\.]+)['\"]", re.I)

# writer.add_scalar("val/mIoU", ...)  ·  wandb.log({"test/mAP": ...})
_METRIC_SINK_RE = re.compile(
    r"(?:add_scalar|add_scalars|wandb\.log|mlflow\.log_metric|self\.log)"
    r"\s*\(\s*\{?\s*['\"]([A-Za-z0-9_/\-\.]+)['\"]", re.I)


def _metric_leaf(name: str) -> str:
    """`val/mIoU` and `test.top1` name one metric; keep the final segment."""
    return re.split(r"[/.]", name.strip())[-1]


_METRIC_KEY_RE = re.compile(
    r"(?:--eval|--metric[s]?|\bmetric[s]?\s*[=:]\s*)\s*\[?[\"']?([A-Za-z0-9_\-]+)", re.I)
_KV_RE = re.compile(r"^\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*[:=]\s*([^,#\n]+)")
_SEED_RE = re.compile(
    r"(?:manual_seed\(|seed_everything\(|set_seed\(|\bseed\b\s*[:=]\s*|--seed[ =])\s*"
    r"['\"]?(\d{1,10})", re.I)


DOC_SUFFIXES = (".md", ".rst", ".txt")


_PY_TRIPLE_RE = re.compile(r'("""|\'\'\')(?:.|\n)*?\1')


def strip_python_prose(text: str) -> str:
    """Blank out `#` comments and triple-quoted blocks in Python source.

    A dataset or metric name inside a docstring is prose, not something the code
    reads, but the file extension says `.py` so `source_kind` calls it a config.
    That is how COCO entered study080's strong facts from a sentence describing
    an OwlViT output format. Newlines are preserved so line numbers in the
    evidence strings stay correct; ordinary string literals are left alone,
    because `default="prompt_templates/imagenet_templates.py"` is a real fact.
    """
    text = _PY_TRIPLE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    out = []
    for line in text.split("\n"):
        i = line.find("#")
        out.append(line if i < 0 else line[:i])
    return "\n".join(out)


def source_kind(path: Path) -> str:
    """How much weight a fact from this file carries.

    `config` facts come from files the code actually reads, so they describe what
    the repository *does*. `docs` facts come from prose, which routinely names
    datasets a paper merely compares against — mmsegmentation's README mentions
    CIFAR-100 in a sentence about Transformers. Only `config` facts may drive a
    conflict; `docs` mentions are recorded separately as weak evidence.
    """
    if path.suffix.lower() in DOC_SUFFIXES:
        return "docs"
    parts = {s.lower() for s in path.parts}
    if any(h in parts for h in CONFIG_DIR_HINTS):
        return "config"
    return "config" if path.suffix.lower() in CONFIG_SUFFIXES else "docs"


def _canon(value: str, table: dict) -> str | None:
    key = re.sub(r"[\s_\-]+", "", value.strip().lower())
    for surface, canonical in table.items():
        if re.sub(r"[\s_\-]+", "", surface) == key:
            return canonical
    return None


def scannable(files):
    """Yield (path, source_kind, text) with Python prose removed.

    Every finder goes through here so the invariant holds no matter how `files`
    was built — collect_files, a test fixture, or a future caller. Doing it in
    collect_files alone left find_datasets() wrong when called directly.
    """
    for path, text in files:
        if path.suffix.lower() == ".py":
            text = strip_python_prose(text)
        yield path, source_kind(path), text


def collect_files(repo_dir: Path) -> list[tuple[Path, str]]:
    """Config, entry-point and documentation files, config directories first."""
    out: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        if p in seen or len(out) >= MAX_FILES or not p.is_file():
            return
        try:
            if p.stat().st_size > MAX_BYTES:
                return
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        seen.add(p)
        out.append((p, txt))

    candidates = [p for p in repo_dir.rglob("*")
                  if p.is_file() and not (SKIP_PARTS & set(p.parts))]

    def rank(p: Path) -> tuple:
        parts = {s.lower() for s in p.parts}
        in_cfg = any(h in parts for h in CONFIG_DIR_HINTS)
        return (0 if in_cfg else 1 if p.suffix.lower() in CONFIG_SUFFIXES else 2,
                len(p.parts))

    # Budget allocation matters on large repositories. mmsegmentation alone has
    # thousands of configs, so a purely config-first fill exhausts the cap before
    # reaching tools/ and scripts/ — exactly where seeds and evaluation commands
    # live. Reserve a quarter of the budget for entry points.
    entry_budget = MAX_FILES // 4

    def is_entry(p: Path) -> bool:
        parts = {s.lower() for s in p.parts}
        return (bool(parts & {"tools", "scripts", "bin"})
                or len(p.relative_to(repo_dir).parts) == 1)

    entries = [p for p in candidates
               if is_entry(p) and p.suffix.lower() in (".py", ".sh", ".md", ".rst")]
    for p in sorted(entries, key=lambda q: len(q.parts))[:entry_budget]:
        add(p)

    for p in sorted(candidates, key=rank):
        if p.suffix.lower() in CONFIG_SUFFIXES or p.suffix.lower() in (".md", ".rst", ".sh"):
            add(p)
    return out


def find_datasets(files) -> tuple[list[dict], list[dict]]:
    """Returns (repo facts from configs, weak mentions from documentation)."""
    strong: "OrderedDict[str, dict]" = OrderedDict()
    weak: "OrderedDict[str, dict]" = OrderedDict()
    for path, kind, text in scannable(files):
        bucket = strong if kind == "config" else weak
        other = weak if kind == "config" else strong
        for m in _DATASET_RE.finditer(text):
            canonical = DATASET_ALIASES.get(m.group(1).lower())
            if not canonical or canonical in bucket:
                continue
            line = text.count("\n", 0, m.start()) + 1
            lines = text.splitlines()
            snippet = lines[line - 1].strip()[:110] if 0 < line <= len(lines) else ""
            bucket[canonical] = {"name": m.group(1), "canonical": canonical,
                                 "source_kind": kind,
                                 "evidence": f"{path.name}:{line}: {snippet}"}
    for k in strong:                       # a config fact outranks a prose mention
        weak.pop(k, None)
    return list(strong.values()), list(weak.values())


def find_metrics(files) -> list[dict]:
    """Metrics the repository can compute, with the signal that found each.

    A metric may be seen several times by different signals. The strongest wins,
    so `metric_never_computed` is decided on a library call where one exists and
    falls back to a logged name only when it does not — and the record says
    which, so a reviewer can judge the claim per signal class.
    """
    found: "OrderedDict[str, dict]" = OrderedDict()

    def offer(canonical, surface, signal, path, text, pos):
        if not canonical:
            return
        prev = found.get(canonical)
        if prev and METRIC_SIGNAL_RANK[prev["signal"]] >= METRIC_SIGNAL_RANK[signal]:
            return
        line = text.count("\n", 0, pos) + 1
        found[canonical] = {"name": surface, "canonical": canonical,
                            "signal": signal,
                            "evidence": f"{path.name}:{line}"}

    for path, _kind, text in scannable(files):
        for m in _METRIC_API_RE.finditer(text):
            offer(METRIC_API[m.group(1)], m.group(1), "metric_api", path, text, m.start())
        for m in _METRIC_LOAD_RE.finditer(text):
            offer(_canon(m.group(1), METRIC_ALIASES), m.group(1),
                  "metric_api", path, text, m.start())
        for m in _METRIC_CFG_RE.finditer(text):
            for surface in _QUOTED_RE.findall(m.group(1)):
                offer(_canon(surface, METRIC_ALIASES), surface,
                      "eval_config", path, text, m.start())
        for m in _METRIC_KEY_RE.finditer(text):
            offer(_canon(m.group(1), METRIC_ALIASES), m.group(1),
                  "cli_flag", path, text, m.start())
        for rx in (_METRIC_LOOKUP_RE, _METRIC_SINK_RE):
            for m in rx.finditer(text):
                leaf = _metric_leaf(m.group(1))
                offer(_canon(leaf, METRIC_ALIASES), leaf,
                      "logged", path, text, m.start())

    return list(found.values())


def _argparse_defaults(text: str) -> list[tuple[str, str]]:
    """Read `parser.add_argument('--lr', default=0.1)` pairs without executing."""
    out = []
    try:
        # We parse third-party source, so their invalid escape sequences ("\s"
        # in a non-raw string) raise SyntaxWarning on Python 3.12+. That is a
        # property of the repository being audited, not of this sweep, and 96
        # repositories' worth of it buries the actual output.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text)
    except Exception:
        return out
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        name = None
        for a in node.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("-"):
                name = a.value.lstrip("-")
                break
        if not name:
            continue
        for kw in node.keywords:
            if kw.arg == "default" and isinstance(kw.value, ast.Constant):
                out.append((name, str(kw.value.value)))
    return out


def find_hyperparameters(files) -> list[dict]:
    found: "OrderedDict[str, dict]" = OrderedDict()
    for path, _kind, text in scannable(files):
        pairs: list[tuple[str, str, int]] = []
        if path.suffix.lower() == ".py":
            pairs += [(k, v, 0) for k, v in _argparse_defaults(text)]
        for i, line in enumerate(text.splitlines(), 1):
            m = _KV_RE.match(line)
            if m:
                pairs.append((m.group(1), m.group(2).strip().strip("'\","), i))
        for name, value, line in pairs:
            canonical = HP_ALIASES.get(name.lower())
            if not canonical or canonical in found:
                continue
            value = (value or "").strip()
            # `optimizer = optimizer` and friends: a key echoing its own name, or
            # a bare type/placeholder, carries no comparable value.
            if not value or value.lower() in {name.lower(), canonical.lower(),
                                              "none", "null", "true", "false", "dict"}:
                continue
            # A variable reference is not a value: `num_classes =
            # model.decode_head.num_classes` tells us nothing comparable.
            if re.search(r"[A-Za-z_]\w*\.[A-Za-z_]", value) or "(" in value:
                continue
            if not re.match(r"^[-+]?[\d.]+(?:[eE][-+]?\d+)?$|^[A-Za-z][\w\-]{0,30}$", value):
                continue
            found[canonical] = {"name": name, "canonical": canonical, "value": value,
                                "evidence": f"{path.name}:{line}" if line else path.name}
    return list(found.values())


def find_seeds(files) -> list[dict]:
    found: "OrderedDict[str, dict]" = OrderedDict()
    for path, _kind, text in scannable(files):
        for m in _SEED_RE.finditer(text):
            v = m.group(1)
            if v in found:
                continue
            line = text.count("\n", 0, m.start()) + 1
            found[v] = {"value": v, "evidence": f"{path.name}:{line}"}
    return list(found.values())


def extract_repo_facts(repo_dir: str | Path) -> dict:
    repo_dir = Path(repo_dir)
    files = collect_files(repo_dir)
    datasets, dataset_mentions = find_datasets(files)
    return {
        "facts_version": FACTS_VERSION,
        "n_files_read": len(files),
        "datasets": datasets,
        "dataset_mentions_docs_only": dataset_mentions,
        "hyperparameters": find_hyperparameters(files),
        "metrics": find_metrics(files),
        "seeds": find_seeds(files),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo_dir")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    out = extract_repo_facts(a.repo_dir)
    for kind in ("datasets", "hyperparameters", "metrics", "seeds"):
        items = out[kind]
        print(f"  {kind:16} n={len(items)}")
        for it in items[:6]:
            label = it.get("canonical") or it.get("value")
            val = f" = {it['value']}" if "value" in it and "canonical" in it else ""
            print(f"      {label}{val}   [{it['evidence'][:70]}]")
    print(f"  ({out['n_files_read']} files read)")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
