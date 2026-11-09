"""Build blind annotation bundles for the N9 inter-annotator agreement study.

The second annotator receives, for each sampled study, a shuffled list of
candidate items with no indication of where each one came from. Candidates are
the union of:

  * the current ground-truth entries  (the first author's KEEP decisions)
  * everything the three open-weight extractors proposed

Because the two sources are merged and shuffled, a KEEP/DISCARD judgement on the
pooled list is a genuine blind replication of the original verification pass.
Items present in the ground truth carry an implicit first-author KEEP; items the
models proposed and the ground truth omits carry an implicit DISCARD. That is a
fixed item set with two labels, so Cohen's kappa is well defined on it.

Nothing in the generated bundle reveals the origin of an item. The mapping is
written to a separate key file that stays with the first author until both sets
are frozen.

Usage
-----
    python3 evaluation/build_annotation_bundles.py            # build everything
    python3 evaluation/build_annotation_bundles.py --calibration   # 3 studies only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GT = os.path.join(ROOT, "data", "ground_truth")
EXTRACT = os.path.join(ROOT, "data", "extractions")
RESULTS = os.path.join(ROOT, "validation", "results")
REPO_LIST = os.path.join(ROOT, "validation", "repo_list.csv")
OUT = os.path.join(ROOT, "evaluation", "annotation_round1")

SAMPLE_SEED = 20261009          # recorded, and fixed before annotation starts
N_SILVER = 8                    # gold tier is taken in full
CALIBRATION_N = 3

# ground-truth entity key -> field name used in the bundle
GOLD_FIELDS = {
    "SoftwareApplication": "dependencies",
    "Dataset": "datasets",
    "Parameter": "hyperparameters",
    "RandomSeed": "random_seeds",
    "EvaluationResult": "evaluation_results",
    "ComputingEnvironment": "environment",
    "Method": "methods",
}
# extractor metadata key -> field name used in the bundle
MODEL_FIELDS = {
    "dependencies": "dependencies",
    "datasets": "datasets",
    "hyperparameters": "hyperparameters",
    "random_seeds": "random_seeds",
    "evaluation_results": "evaluation_results",
    "hardware": "environment",
    "methods": "methods",
}

FIELD_ORDER = [
    "dependencies", "datasets", "hyperparameters", "random_seeds",
    "evaluation_results", "environment", "methods",
]


# ---------------------------------------------------------------- rendering

_NULLISH = {
    "", "null", "none", "n/a", "na", "unknown", "unspecified", "string",
    "not specified", "not stated", "exact version not specified",
    "version not specified", "latest",
}


def _s(v):
    if v is None:
        return ""
    return str(v).strip()


def _clean(v):
    """Blank out schema placeholders the extractors sometimes emit verbatim."""
    t = _s(v)
    return "" if t.lower() in _NULLISH else t


def render(field: str, item) -> str:
    """Human-readable one-line form of a candidate item."""
    if not isinstance(item, dict):
        return _s(item)
    if field == "dependencies":
        ver = _clean(item.get("version"))
        name = _s(item.get("name"))
        return f"{name}  [version: {ver or 'not stated'}]"
    if field == "datasets":
        name = _s(item.get("name"))
        extra = _clean(item.get("version")) or _clean(item.get("role"))
        return f"{name}" + (f"  [{extra}]" if extra else "")
    if field == "hyperparameters":
        return f"{_s(item.get('name'))} = {_clean(item.get('value')) or 'not stated'}"
    if field == "random_seeds":
        val = _s(item.get("value")) or _s(item.get("seed")) or _s(item.get("name"))
        where = _s(item.get("scope")) or _s(item.get("context"))
        return f"seed = {val}" + (f"  [{where}]" if where else "")
    if field == "evaluation_results":
        parts = [f"{_s(item.get('metric'))} = {_s(item.get('value'))}"]
        split = _s(item.get("split"))
        ds = _s(item.get("dataset"))
        tail = ", ".join(p for p in (split, ds) if p)
        if tail:
            parts.append(f"[{tail}]")
        return "  ".join(parts)
    if field == "methods":
        return _s(item.get("name"))
    return json.dumps(item, ensure_ascii=False)


def canon(field: str, rendered: str) -> str:
    """Dedup key. Deliberately loose: near-duplicates collapse into one row."""
    key = rendered.lower()
    for ch in "_-/\\ \t":
        key = key.replace(ch, "")
    return f"{field}::{key}"


def environment_items(blob):
    """ComputingEnvironment / hardware are dicts: one candidate per stated key."""
    out = []
    if isinstance(blob, dict):
        for k, v in blob.items():
            val = _s(v)
            if _clean(val):
                out.append(f"{k}: {val}")
    elif isinstance(blob, list):
        for entry in blob:
            out.extend(environment_items(entry))
    return out


# ---------------------------------------------------------------- loading

def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def gold_path(study_id):
    for tier in ("gold", "silver"):
        p = os.path.join(GT, tier, study_id, "gold_standard.json")
        if os.path.exists(p):
            return p, tier
    return None, None


def study_candidates(study_id):
    """{field: [rendered, ...]} merged from ground truth and all extractors."""
    pool = {f: {} for f in FIELD_ORDER}          # canon -> rendered

    gp, _ = gold_path(study_id)
    gold = load_json(gp) if gp else None
    gold_keys = set()
    if gold:
        for gkey, field in GOLD_FIELDS.items():
            entries = (gold.get("entities") or {}).get(gkey) or []
            if field == "environment":
                rendered_list = environment_items(entries)
            else:
                rendered_list = [render(field, it) for it in entries]
            for r in rendered_list:
                if not r.strip():
                    continue
                c = canon(field, r)
                pool[field].setdefault(c, r)
                gold_keys.add(c)

    for fname in sorted(os.listdir(EXTRACT)):
        if not fname.startswith(study_id + "__"):
            continue
        blob = load_json(os.path.join(EXTRACT, fname))
        meta = (blob or {}).get("metadata") or {}
        for mkey, field in MODEL_FIELDS.items():
            entries = meta.get(mkey)
            if entries is None:
                continue
            if field == "environment":
                rendered_list = environment_items(entries)
            else:
                rendered_list = [render(field, it) for it in (entries or [])]
            for r in rendered_list:
                if not r.strip():
                    continue
                pool[field].setdefault(canon(field, r), r)

    return pool, gold_keys


# ---------------------------------------------------------------- sampling

def fair_r_score(study_id):
    blob = load_json(os.path.join(RESULTS, f"{study_id}.json")) or {}
    return ((blob.get("fair_r") or {}).get("total_score"))


def select_sample():
    gold_ids = sorted(os.listdir(os.path.join(GT, "gold")))
    silver_ids = sorted(os.listdir(os.path.join(GT, "silver")))
    silver_ids = [s for s in silver_ids if s not in gold_ids]

    scored, unscored = [], []
    for sid in silver_ids:
        sc = fair_r_score(sid)
        (scored if sc is not None else unscored).append((sid, sc))
    scored.sort(key=lambda t: t[1])

    rng = random.Random(SAMPLE_SEED)
    picks, bands = [], 4
    if scored:
        size = max(1, len(scored) // bands)
        per_band = N_SILVER // bands
        for b in range(bands):
            lo = b * size
            hi = len(scored) if b == bands - 1 else (b + 1) * size
            chunk = [sid for sid, _ in scored[lo:hi]]
            rng.shuffle(chunk)
            picks.extend(chunk[:per_band])
    leftover = [sid for sid, _ in scored if sid not in picks] + [s for s, _ in unscored]
    rng.shuffle(leftover)
    while len(picks) < N_SILVER and leftover:
        picks.append(leftover.pop())

    return gold_ids, sorted(picks)


# ---------------------------------------------------------------- writing

def repo_rows():
    rows = {}
    if os.path.exists(REPO_LIST):
        with open(REPO_LIST, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                rows[row.get("study_id", "").strip()] = row
    return rows


def write_bundle(study_id, info, order_index):
    folder = os.path.join(OUT, f"{order_index:02d}_{study_id}")
    os.makedirs(folder, exist_ok=True)

    pool, gold_keys = study_candidates(study_id)

    rows, key_rows = [], []
    n = 0
    for field in FIELD_ORDER:
        items = sorted(pool[field].items())
        rng = random.Random(f"{SAMPLE_SEED}:{study_id}:{field}")
        rng.shuffle(items)
        for c, rendered in items:
            n += 1
            item_id = f"{study_id}-{n:03d}"
            rows.append({
                "item_id": item_id, "field": field, "item": rendered,
                "decision": "", "note": "",
            })
            key_rows.append({
                "item_id": item_id, "field": field, "item": rendered,
                "in_ground_truth": "yes" if c in gold_keys else "no",
            })

    with open(os.path.join(folder, "annotate.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["item_id", "field", "item", "decision", "note"])
        w.writeheader()
        w.writerows(rows)

    with open(os.path.join(folder, "additions.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["field", "item", "where_you_found_it"])
        w.writeheader()

    title = (info.get("paper_title") or "").strip()
    with open(os.path.join(folder, "STUDY.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# {study_id}\n\n")
        if title:
            fh.write(f"**{title}**\n\n")
        for label, key in (("Paper", "paper_url"), ("PDF", "paper_url_pdf"),
                           ("Repository", "repo_url")):
            val = (info.get(key) or "").strip()
            if val:
                fh.write(f"- {label}: {val}\n")
        fh.write(f"\n{len(rows)} items to judge in `annotate.csv`.\n")
        fh.write("\nRead the paper and the repository, then mark every row K, D or U. "
                 "Put anything you find that is not listed into `additions.csv`.\n")

    return rows, key_rows, folder


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibration", action="store_true",
                    help=f"build only the first {CALIBRATION_N} studies")
    ap.add_argument("--skip-fields", default="",
                    help="comma-separated fields to leave out, e.g. methods")
    args = ap.parse_args()

    if args.skip_fields:
        for f in [x.strip() for x in args.skip_fields.split(",") if x.strip()]:
            if f in FIELD_ORDER:
                FIELD_ORDER.remove(f)

    gold_ids, silver_ids = select_sample()
    selected = gold_ids + silver_ids
    if args.calibration:
        selected = selected[:CALIBRATION_N]

    os.makedirs(OUT, exist_ok=True)
    info_by_id = repo_rows()

    all_keys, totals = [], {}
    for i, sid in enumerate(selected, start=1):
        rows, key_rows, folder = write_bundle(sid, info_by_id.get(sid, {}), i)
        all_keys.extend(key_rows)
        totals[sid] = len(rows)
        print(f"  {os.path.basename(folder):<24} {len(rows):>4} items")

    import shutil
    docs_dir = os.path.join(ROOT, "docs", "annotation")
    for doc in ("CODEBOOK.md", "README.md"):
        src = os.path.join(docs_dir, doc)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(OUT, doc))

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_seed": SAMPLE_SEED,
        "gold_studies": gold_ids,
        "silver_studies": silver_ids,
        "calibration_only": bool(args.calibration),
        "items_per_study": totals,
        "total_items": sum(totals.values()),
        "ground_truth_digest": digest_ground_truth(selected),
    }
    with open(os.path.join(OUT, "SAMPLE.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    key_dir = os.path.join(ROOT, "evaluation", "annotation_round1_key")
    os.makedirs(key_dir, exist_ok=True)
    with open(os.path.join(key_dir, "origin_key.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["item_id", "field", "item", "in_ground_truth"])
        w.writeheader()
        w.writerows(all_keys)

    print(f"\n{len(selected)} studies, {manifest['total_items']} items")
    print(f"bundle : {OUT}")
    print(f"key    : {key_dir}  (do NOT send this to the annotator)")


def digest_ground_truth(study_ids):
    h = hashlib.sha256()
    for sid in sorted(study_ids):
        p, _ = gold_path(sid)
        if p and os.path.exists(p):
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


if __name__ == "__main__":
    main()
