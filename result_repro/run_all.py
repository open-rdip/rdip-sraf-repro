"""End-to-end, engine-driven result-level reproduction (streaming).

For every non-skipped study in the manifest, this does the whole thing and keeps
only the small comparison values:

  clone -> extract execution recipe (or reuse data/recipes/<study>.json)
        -> build venv + run the recipe's command (time + disk capped)
        -> read the obtained metric off the log (LLM, heuristic fallback)
        -> compare obtained vs the paper's claimed number
        -> DELETE the clone / venv / any downloaded data (streaming)

Persists only: result_repro/results/summary.{json,csv} (the funnel + per-study
comparison) and per-study markers for resumability. Heavy artifacts never survive.

Run it as one GPU job (see run_all.sbatch), with a local LLM served (vLLM):

  ~/envs/sraf/bin/python -m result_repro.run_all --backend vllm --model <repo>
      [--study study002] [--run-timeout 2700] [--disk-cap 40] [--no-llm-parse] [--force]

Cluster policy = one job; this loops sequentially and is resumable.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from rag_pipeline.recipe_extractor import (read_repo_text, extract_recipe,   # noqa: E402
                                           parse_metrics_from_log)
from result_repro.compare_results import compare_entry                       # noqa: E402

RECIPES_DIR = os.path.join(ROOT, "data", "recipes")
GOLD_DIR = os.path.join(ROOT, "result_repro", "gold_recipes")
RESULTS_DIR = os.path.join(ROOT, "result_repro", "results")
ROWS_DIR = os.path.join(RESULTS_DIR, "rows")
LOGS_DIR = os.path.join(RESULTS_DIR, "logs")


def _s(x):
    return "" if x is None else str(x).strip()


PLACEHOLDER_RE = re.compile(
    r"/path/to|/path_to|path_to_|\$\{?checkpoint|<checkpoint|/your/|/PATH/|"
    r"checkpoint[ _]path|/tmp/outdir|/path\b", re.I)


def classify_failure(log: str) -> str:
    """Bucket a run_error log into the paper's blocker taxonomy."""
    low = log.lower()
    if "mujoco" in low:
        return "missing_system_dep:mujoco"
    if "unzip: not found" in low or "unzip: command not found" in low:
        return "missing_tool:unzip"
    if "404 not found" in low or "error 404" in low:
        return "dead_download:404"
    if "500 internal server error" in low or "error 500" in low:
        return "dead_download:500"
    if "403" in low and ("download" in low or "drive.google" in low or "usercontent" in low):
        return "gated_download:403"
    if "cuda out of memory" in low or "out of memory" in low:
        return "gpu_oom"
    if "host key verification" in low or "git@github.com" in log or \
            ("permission denied" in low and "publickey" in low):
        return "auth_ssh"
    m = re.search(r"no module named '([^']+)'", log, re.I)
    if m:
        return f"missing_dependency:{m.group(1)}"
    if "failed to build" in low and "editable" in low:
        return "install_build_error"
    if "configuration error: `project`" in low or "invalid pyproject.toml" in low:
        return "install_build_error"
    if "no such file or directory" in low:
        return "missing_file_or_data"
    return "run_error:other"


def _du_gb(path: str) -> float:
    total = 0
    for dp, _, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total / 1e9


def _pick_python() -> str:
    for cand in (os.path.expanduser("~/pys/py310/bin/python"),
                 os.path.expanduser("~/pys/py39/bin/python"), "python3"):
        if cand == "python3" or os.path.exists(cand):
            return cand
    return "python3"


def _clone(url: str, dst: str) -> bool:
    try:
        subprocess.run(["git", "clone", "--depth", "1", url, dst],
                       check=True, capture_output=True, timeout=300)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _sh(cmd: str, cwd: str, timeout: int, env: dict, log: list):
    """Run a shell command, tee output into log; return returncode or 'timeout'."""
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, env=env, text=True,
                           capture_output=True, timeout=timeout)
        log.append(f"$ {cmd}\n{p.stdout[-4000:]}\n{p.stderr[-2000:]}")
        return p.returncode
    except subprocess.TimeoutExpired:
        log.append(f"$ {cmd}\n[TIMEOUT after {timeout}s]")
        return "timeout"


def run_experiment(repo_dir: str, recipe: dict, run_to: int, setup_to: int,
                   cap_gb: float):
    """Build a venv, stage per the recipe, run the command. Returns (log, outcome, reason)."""
    log: list[str] = []
    cmd = recipe.get("run_command")
    if not cmd:
        return "", "no_recipe", "recipe had no run command"

    subprocess.run([_pick_python(), "-m", "venv", ".venv"], cwd=repo_dir,
                   capture_output=True, text=True)
    venv_bin = os.path.join(repo_dir, ".venv", "bin")
    env = dict(os.environ)
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = os.path.join(repo_dir, ".venv")

    # some nodes lack `unzip`; provide a shim so a recipe's unzip step isn't OUR failure
    try:
        shim = os.path.join(venv_bin, "unzip")
        with open(shim, "w") as f:
            f.write("#!/usr/bin/env python3\n"
                    "import sys, zipfile\n"
                    "a=sys.argv[1:]; zp=None; dest='.'; i=0\n"
                    "while i < len(a):\n"
                    "    if a[i]=='-d': dest=a[i+1]; i+=2; continue\n"
                    "    if a[i].startswith('-'): i+=1; continue\n"
                    "    zp = zp or a[i]; i+=1\n"
                    "zipfile.ZipFile(zp).extractall(dest)\n")
        os.chmod(shim, 0o755)
    except OSError:
        pass

    _sh("python -m pip install -q --upgrade pip", repo_dir, 300, env, log)
    if os.path.isfile(os.path.join(repo_dir, "requirements.txt")):
        _sh("python -m pip install -q -r requirements.txt", repo_dir, setup_to, env, log)
    if os.path.isfile(os.path.join(repo_dir, "setup.py")) or \
            os.path.isfile(os.path.join(repo_dir, "pyproject.toml")):
        _sh("python -m pip install -q -e .", repo_dir, setup_to, env, log)

    # Run the recipe's setup steps + command as ONE shell script, so `cd` and
    # `export` from setup persist into the run command (real recipes are multi-line).
    steps = [str(s) for s in (recipe.get("setup_steps") or []) if s]
    script = "\n".join(steps + [cmd])
    rc = _sh(script, repo_dir, setup_to + run_to, env, log)
    if _du_gb(repo_dir) > cap_gb:
        return "\n".join(log), "data_too_large", f"scratch exceeded {cap_gb} GB"
    if rc == "timeout":
        return "\n".join(log), "run_timeout", f"run exceeded {setup_to + run_to}s"
    if rc != 0:
        return "\n".join(log), "run_error", f"run exited {rc}"
    return "\n".join(log), "ran", ""


def heuristic_metrics(log: str, claimed: list) -> list:
    """Fallback: regex a number near each claimed metric name (last occurrence)."""
    out = []
    for c in claimed or []:
        m = _s(c.get("metric"))
        if not m:
            continue
        tok = re.escape(m.split()[0])
        found = re.findall(tok + r"[^0-9\-]{0,20}(-?\d+\.?\d*)%?", log, re.I)
        if found:
            out.append({"metric": c.get("metric"), "value": found[-1],
                        "split": c.get("split")})
    return out


def process_study(entry: dict, backend, model, args) -> dict:
    sid = entry["study_id"]
    if entry.get("status") == "skipped":
        return {"study_id": sid, "status": "skipped",
                "reason": (entry.get("run") or {}).get("notes", ""), "pairs": []}

    row = {"study_id": sid, "repo_url": entry.get("repo_url"),
           "claimed": entry.get("claimed") or [], "obtained": [], "pairs": [],
           "recipe_command": None, "recipe_confidence": None}
    scratch = tempfile.mkdtemp(prefix=f"repro-{sid}-", dir=args.scratch)
    repo = os.path.join(scratch, "repo")
    try:
        if not _clone(entry.get("repo_url"), repo):
            row.update(status="run_failed", reason="clone_failed"); return row

        # a hand-written GOLD recipe (if present) takes priority: it lets us test
        # the execution/compare harness independently of autonomous extraction.
        gold = os.path.join(GOLD_DIR, f"{sid}.json")
        rp = os.path.join(RECIPES_DIR, f"{sid}.json")
        if os.path.isfile(gold):
            recipe = json.load(open(gold))
            row["recipe_source"] = "gold"
        elif os.path.isfile(rp) and not args.reextract:
            recipe = json.load(open(rp))
            row["recipe_source"] = "extracted"
        elif args.no_llm_parse:
            # run phase: no LLM available; recipe must have been extracted in phase 1
            row.update(status="run_failed",
                       reason="recipe_missing (run extract_recipes first)")
            return row
        else:
            recipe = extract_recipe(read_repo_text(repo), backend=backend, model=model)
            recipe["study_id"], recipe["repo_url"] = sid, entry.get("repo_url")
            os.makedirs(RECIPES_DIR, exist_ok=True)
            json.dump(recipe, open(rp, "w"), indent=2)
            row["recipe_source"] = "extracted"
        row["recipe_command"] = recipe.get("run_command")
        row["recipe_confidence"] = recipe.get("confidence")

        # a command that is only a placeholder is not runnable — don't waste a run
        if PLACEHOLDER_RE.search(recipe.get("run_command") or ""):
            row.update(status="run_failed", reason="placeholder_recipe"); return row

        log, outcome, reason = run_experiment(
            repo, recipe, args.run_timeout, args.setup_timeout, args.disk_cap)
        # keep a small log tail so failures are debuggable (and LLM-parseable later)
        os.makedirs(LOGS_DIR, exist_ok=True)
        open(os.path.join(LOGS_DIR, f"{sid}.log"), "w").write(log[-40000:])
        row["log_tail"] = log[-1500:]
        if outcome != "ran":
            if outcome == "run_error":
                reason = classify_failure(log)     # fine-grained taxonomy from the log
            row.update(status="run_failed", reason=reason); return row

        obtained = []
        if not args.no_llm_parse:
            obtained = parse_metrics_from_log(log, row["claimed"], backend=backend, model=model)
        if not obtained:
            obtained = heuristic_metrics(log, row["claimed"])
        row["obtained"] = obtained

        cmp = compare_entry({"study_id": sid, "claimed": row["claimed"],
                             "obtained": obtained, "status": "pending"},
                            args.tol, args.abs_tol)
        row["status"] = cmp["status"] if obtained else "run_failed"
        row["reason"] = "" if obtained else "no_metric_in_log"
        row["pairs"] = cmp.get("pairs", [])
        return row
    except Exception as e:  # noqa: BLE001 — never let one repo kill the sweep
        row.update(status="run_failed", reason=f"exception: {e}")
        return row
    finally:
        shutil.rmtree(scratch, ignore_errors=True)   # streaming: delete the heavy stuff


def summarise(rows: list) -> dict:
    status = Counter(r["status"] for r in rows)
    reasons = Counter(r.get("reason", "") for r in rows
                      if r["status"] in ("skipped", "run_failed") and r.get("reason"))
    ran = [r for r in rows if r["status"] in ("reproduced", "partial", "mismatch")]
    got_recipe = [r for r in rows if r.get("recipe_command")]
    return {
        "n_total": len(rows),
        "n_recipe_extracted": len(got_recipe),
        "n_ran": len(ran),
        "n_reproduced": status.get("reproduced", 0),
        "reproduced_of_ran": round(status.get("reproduced", 0) / len(ran), 3) if ran else None,
        "status_counts": dict(status),
        "blocker_taxonomy": dict(reasons),
    }


def write_outputs(rows: list):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    summ = summarise(rows)
    json.dump({"summary": summ, "rows": rows},
              open(os.path.join(RESULTS_DIR, "summary.json"), "w"), indent=2)
    with open(os.path.join(RESULTS_DIR, "summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["study_id", "status", "reason", "recipe_confidence",
                    "claimed", "obtained"])
        for r in rows:
            w.writerow([r["study_id"], r["status"], r.get("reason", ""),
                        r.get("recipe_confidence", ""),
                        "; ".join(f"{c.get('metric')}={c.get('claimed')}" for c in r.get("claimed", [])),
                        "; ".join(f"{o.get('metric')}={o.get('value')}" for o in r.get("obtained", []))])
    return summ


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=os.path.join(ROOT, "result_repro", "manifest.yaml"))
    ap.add_argument("--backend", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--study", default=None, help="restrict to one study id")
    ap.add_argument("--scratch", default=os.getenv("SRAF_SCRATCH_DIR", "/tmp"))
    ap.add_argument("--run-timeout", type=int, default=2700, dest="run_timeout")
    ap.add_argument("--setup-timeout", type=int, default=1800, dest="setup_timeout")
    ap.add_argument("--disk-cap", type=float, default=40.0, dest="disk_cap", help="GB")
    ap.add_argument("--tol", type=float, default=0.05)
    ap.add_argument("--abs-tol", type=float, default=0.01)
    ap.add_argument("--server-wait", type=int, default=1200, dest="server_wait",
                    help="seconds to wait for the LLM server to load (default 1200)")
    ap.add_argument("--no-llm-parse", action="store_true", help="regex-only metric parse")
    ap.add_argument("--reextract", action="store_true", help="ignore cached recipes")
    ap.add_argument("--force", action="store_true", help="ignore per-study markers")
    a = ap.parse_args()

    # --- preflight: wait for the LLM backend to come up (24B models load slowly) ---
    if not a.no_llm_parse and (a.backend or "").lower() in ("vllm", "llamacpp"):
        import time
        import urllib.request
        from config import VLLM_SERVER_URL, LLAMACPP_SERVER_URL
        url = (VLLM_SERVER_URL if (a.backend or "").lower() == "vllm"
               else LLAMACPP_SERVER_URL).rstrip("/") + "/v1/models"
        print(f"Waiting for LLM server at {url} (up to {a.server_wait}s) ...")
        deadline, ok = time.time() + a.server_wait, False
        while time.time() < deadline:
            try:
                urllib.request.urlopen(url, timeout=8)
                ok = True
                break
            except Exception:  # noqa: BLE001
                time.sleep(10)
        if not ok:
            print(f"\nERROR: LLM server still not reachable at {url} after "
                  f"{a.server_wait}s.\nvLLM must be serving on a GPU node. Submit\n"
                  f"  sbatch result_repro/run_all.sbatch\n"
                  f"or start vLLM on a GPU node first (set VLLM_SERVER_URL).\n"
                  f"(The login node has no GPU, so it cannot serve the model.)")
            return 2
        print("  LLM server is up.")

    os.makedirs(ROWS_DIR, exist_ok=True)
    entries = yaml.safe_load(open(a.manifest)) or []
    todo = [e for e in entries if (not a.study or e["study_id"] == a.study)]
    print(f"Result-level reproduction over {len(todo)} studies "
          f"(run-timeout {a.run_timeout}s, disk-cap {a.disk_cap} GB)")

    rows = []
    for e in todo:
        sid = e["study_id"]
        mark = os.path.join(ROWS_DIR, f"{sid}.json")
        if os.path.isfile(mark) and not a.force:
            rows.append(json.load(open(mark)))
            print(f"[{sid}] cached -> {rows[-1]['status']}")
            continue
        print(f"\n[{sid}] {e.get('repo_url')}")
        row = process_study(e, a.backend, a.model, a)
        json.dump(row, open(mark, "w"), indent=2)
        rows.append(row)
        print(f"[{sid}] -> {row['status']} {row.get('reason','')}")
        write_outputs(rows)   # checkpoint after every study

    summ = write_outputs(rows)
    print("\n=== SUMMARY ===")
    print(f"  recipe extracted : {summ['n_recipe_extracted']}/{summ['n_total']}")
    print(f"  ran              : {summ['n_ran']}")
    print(f"  reproduced       : {summ['n_reproduced']}"
          + (f"  ({summ['reproduced_of_ran']:.0%} of ran)" if summ['reproduced_of_ran'] is not None else ""))
    print(f"  status           : {summ['status_counts']}")
    print(f"  blockers         : {summ['blocker_taxonomy']}")
    print(f"\n  -> {RESULTS_DIR}/summary.json + summary.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
