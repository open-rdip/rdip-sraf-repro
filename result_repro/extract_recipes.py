"""Engine-driven execution-recipe extraction for the runnable full-tier repos.

For each non-skipped study in result_repro/manifest.yaml, clone the repo, read its
documentation, and have the LLM extract the execution recipe (how to reproduce the
headline metric). Writes data/recipes/<study>.json and, with --map, appends an
rdip:ExecutionRecipe to the study graph. The run harness then executes the
EXTRACTED command — no hand-written commands.

Prereq: an LLM backend (local vLLM recommended, same as the corpus extraction).
Oxigraph only needed for --map.

  ~/envs/sraf/bin/python -m result_repro.extract_recipes \
      --backend vllm --model <repo> [--study study002] [--map]

Runs over all non-skipped studies by default; --study restricts to one.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from rag_pipeline.recipe_extractor import read_repo_text, extract_recipe  # noqa: E402
from rag_pipeline.mapper import map_recipe, to_turtle                     # noqa: E402

GRAPH_BASE = "https://w3id.org/rdip/graph"
RECIPES_DIR = os.path.join(ROOT, "data", "recipes")


def _clone(url: str, dst: str) -> bool:
    try:
        subprocess.run(["git", "clone", "--depth", "1", url, dst],
                       check=True, capture_output=True, timeout=300)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"   clone failed: {e}")
        return False


def process(entry: dict, backend: str, model: str, do_map: bool) -> dict | None:
    study, url = entry["study_id"], entry.get("repo_url")
    print(f"\n[{study}] {url}")
    if not url:
        return None
    scratch = tempfile.mkdtemp(prefix="recipe-")
    try:
        if not _clone(url, os.path.join(scratch, "repo")):
            return None
        text = read_repo_text(os.path.join(scratch, "repo"))
        if not text.strip():
            print("   no documentation found in repo")
        recipe = extract_recipe(text, backend=backend, model=model)
        recipe["study_id"], recipe["repo_url"] = study, url
        os.makedirs(RECIPES_DIR, exist_ok=True)
        out = os.path.join(RECIPES_DIR, f"{study}.json")
        json.dump(recipe, open(out, "w"), indent=2)
        cmd = recipe.get("run_command")
        print(f"   confidence={recipe.get('confidence')}  command={cmd!r}")
        if do_map:
            from triplestore_client import append_graph
            append_graph(f"{GRAPH_BASE}/{study}", to_turtle(map_recipe(study, recipe)))
            print(f"   mapped rdip:ExecutionRecipe -> <{GRAPH_BASE}/{study}>")
        return recipe
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=os.path.join(ROOT, "result_repro", "manifest.yaml"))
    ap.add_argument("--backend", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--study", default=None, help="restrict to one study id")
    ap.add_argument("--map", action="store_true", help="append recipe to the study graph")
    a = ap.parse_args()

    entries = yaml.safe_load(open(a.manifest)) or []
    todo = [e for e in entries if e.get("status") != "skipped"
            and (not a.study or e["study_id"] == a.study)]
    print(f"Extracting recipes for {len(todo)} studies "
          f"(backend={a.backend}, model={a.model})")

    got = 0
    for e in todo:
        r = process(e, a.backend, a.model, a.map)
        got += bool(r and r.get("run_command"))
    print(f"\nDone: {got}/{len(todo)} studies got a run command. "
          f"Recipes in {RECIPES_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
