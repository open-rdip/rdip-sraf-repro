"""Process ONE repository end to end, holding nothing on the home volume but
the resulting triples and a results record.

Flow:  clone (shallow, to scratch) -> find artifacts -> lift -> build-test
       -> FAIR-R score -> export .ttl + results JSON -> delete clone.

Run one of these per Slurm array task. Each task talks to its OWN Oxigraph
(scratch store, unique port — see run_corpus.sbatch), so concurrent tasks never
contend over the durable triplestore. Graphs are merged into the durable store
later by merge_results.py.

Usage:
  python -m build_harness.process_repo --study-id study007 \
      --repo-url https://github.com/org/name --scratch /tmp/$SLURM_JOB_ID
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# repo root on path so the lifter / scorer / client imports resolve
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from build_harness.artifact_finder import find_artifacts          # noqa: E402
from build_harness.build_tester import run_build_test             # noqa: E402
from build_harness.repo_metadata import extract_repo_metadata     # noqa: E402
from build_harness.python_version import (                        # noqa: E402
    resolve_python_version, choose_interpreter,
)

# PyTorch/CUDA wheels live on the PyTorch index; include a few common CUDA
# builds plus CPU so `torch==x+cuYYY` pins resolve. Override via env.
PYTORCH_INDEXES = [u for u in os.getenv(
    "SRAF_PYTORCH_INDEXES",
    "https://download.pytorch.org/whl/cu121,"
    "https://download.pytorch.org/whl/cu118,"
    "https://download.pytorch.org/whl/cpu").split(",") if u]
# Import parser/mapper submodules directly — NOT lifter.lifter, whose top-level
# imports assume lifter/ is the script dir.
from lifter.parsers.docker_parser import parse_dockerfile         # noqa: E402
from lifter.parsers.conda_parser import from_repo as conda_from_repo  # noqa: E402
from lifter.parsers.pip_parser import from_repo as pip_from_repo  # noqa: E402
from lifter.mapper.rdip_mapper import (                           # noqa: E402
    map_docker, map_conda, map_pip, map_repo_metadata, merge_graphs, to_turtle,
)
from triplestore_client import upload_graph, fetch_graph, count_triples  # noqa: E402
from dashboard.fair_r_scorer import compute_fair_r                # noqa: E402
from config import OUTPUT_DIR                                     # noqa: E402

# Match the graph URI used by the lifter AND the scorer exactly.
def graph_uri(study_id: str) -> str:
    return f"https://w3id.org/rdip/graph/{study_id}"


def _clone(repo_url: str, dest: str) -> bool:
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, dest],
            check=True, capture_output=True, text=True, timeout=600,
        )
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[process_repo] clone failed: {e}")
        return False


def _lift(study_id: str, repo_dir: str, artifacts: dict, repo_meta: dict) -> dict:
    """Lift each artifact from its real location + repo metadata, merge, upload."""
    by_type = artifacts["by_type"]
    graphs, lifted = [], {}

    # Repo-level metadata (identifier / license / commit) — no env files needed,
    # so this lifts even repos with no artifacts at all.
    graphs.append(map_repo_metadata(study_id, repo_meta))

    if "docker" in by_type:
        try:
            parsed = parse_dockerfile(str(Path(repo_dir) / by_type["docker"]))
            graphs.append(map_docker(study_id, parsed)); lifted["docker"] = by_type["docker"]
        except Exception as e:  # noqa: BLE001
            print(f"[process_repo] docker lift skipped: {e}")

    if "conda" in by_type:
        conda_dir = str((Path(repo_dir) / by_type["conda"]).parent)
        parsed = conda_from_repo(conda_dir)
        if parsed:
            graphs.append(map_conda(study_id, parsed)); lifted["conda"] = by_type["conda"]

    if "pip" in by_type:
        pip_dir = str((Path(repo_dir) / by_type["pip"]).parent)
        parsed = pip_from_repo(pip_dir)
        if parsed:
            graphs.append(map_pip(study_id, parsed)); lifted["pip"] = by_type["pip"]

    triples = 0
    if graphs:
        merged = merge_graphs(*graphs)
        upload_graph(graph_uri(study_id), to_turtle(merged))
        triples = count_triples(graph_uri(study_id))

    return {"lifted": lifted, "triples": triples, "n_sources": len(graphs)}


def process(study_id: str, repo_url: str, scratch: str,
            keep: bool = False, build_timeout: int = 1800) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    clone_dir = os.path.join(scratch, study_id)
    record = {
        "study_id": study_id, "repo_url": repo_url, "started": started,
        "status": "ok", "stage": None,
    }

    # 1. clone
    if not _clone(repo_url, clone_dir):
        record.update(status="clone_failed", stage="clone")
        return _persist(record, study_id, None)

    try:
        # 2. find artifacts + repo-level metadata
        artifacts = find_artifacts(clone_dir)
        record["artifacts"] = {
            "by_type": artifacts["by_type"],
            "depth_note": artifacts["depth_note"],
            "n_found": len(artifacts["all"]),
            "all": artifacts["all"],
        }
        repo_meta = extract_repo_metadata(clone_dir, repo_url)
        record["repo_meta"] = repo_meta

        # 3. lift (env artifacts + repo metadata)
        record["lift"] = _lift(study_id, clone_dir, artifacts, repo_meta)

        # 3b. resolve the repo's DECLARED Python version -> interpreter
        pyver, pysrc = resolve_python_version(clone_dir, artifacts)
        interp, pyused, ladder_ok = choose_interpreter(pyver)
        record["python"] = {"declared": pyver, "source": pysrc,
                            "used": pyused, "ladder_available": ladder_ok}

        # 4. build-test (containerless venv, declared Python + PyTorch index)
        record["build"] = run_build_test(
            clone_dir, artifacts, scratch, timeout=build_timeout,
            base_python=interp, extra_index=PYTORCH_INDEXES)

        # 5. FAIR-R score (queries the graph we just uploaded)
        if record["lift"]["triples"] > 0:
            try:
                res = compute_fair_r(study_id)
                record["fair_r"] = {
                    "total_score": res["total_score"], "tier": res["tier"],
                    "dimension_scores": {k: v["score"]
                                         for k, v in res["dimension_scores"].items()},
                    "recommendations": res["recommendations"],
                }
            except Exception as e:  # noqa: BLE001
                record["fair_r"] = {"error": str(e)}
        else:
            record["status"] = "no_artifacts"
    except Exception as e:  # noqa: BLE001
        record.update(status="error", stage="processing", error=str(e))

    record["duration_s"] = round(time.time() - t0, 1)
    out = _persist(record, study_id,
                   graph_uri(study_id) if record.get("lift", {}).get("triples") else None)

    # 6. delete the clone (the whole point of streaming)
    if not keep:
        shutil.rmtree(clone_dir, ignore_errors=True)
    return out


def _persist(record: dict, study_id: str, gref: str | None) -> dict:
    """Write results JSON to home, and export the named graph .ttl if present."""
    results_dir = Path(OUTPUT_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"{study_id}.json").write_text(json.dumps(record, indent=2))

    if gref:
        exports = Path(os.getenv("SRAF_EXPORT_DIR",
                                 str(REPO_ROOT.parent / "triplestore" / "exports")))
        exports.mkdir(parents=True, exist_ok=True)
        try:
            g = fetch_graph(gref)
            g.serialize(destination=str(exports / f"{study_id}.ttl"), format="turtle")
        except Exception as e:  # noqa: BLE001
            print(f"[process_repo] export failed: {e}")
    return record


def main():
    ap = argparse.ArgumentParser(description="SRAF build harness — process one repo")
    ap.add_argument("--study-id", required=True)
    ap.add_argument("--repo-url", required=True)
    ap.add_argument("--scratch", default=os.getenv("SRAF_SCRATCH_DIR", "/tmp/sraf"))
    ap.add_argument("--build-timeout", type=int, default=1800)
    ap.add_argument("--keep", action="store_true", help="don't delete the clone")
    args = ap.parse_args()

    os.makedirs(args.scratch, exist_ok=True)
    rec = process(args.study_id, args.repo_url, args.scratch,
                  keep=args.keep, build_timeout=args.build_timeout)
    b = rec.get("build", {})
    print(f"\n[process_repo] {args.study_id}: status={rec['status']} "
          f"triples={rec.get('lift', {}).get('triples', 0)} "
          f"resolve={b.get('resolve_success')} build={b.get('build_success')} "
          f"fair_r={rec.get('fair_r', {}).get('total_score')}")


if __name__ == "__main__":
    main()
