"""Re-score existing study graphs with the current FAIR-R scorer.

No re-clone, no re-build: the repository graphs are already in Oxigraph, so we
just recompute FAIR-R over them and rewrite the `fair_r` field in each result
JSON. Build/resolve outcomes are left untouched.

Requires a running Oxigraph serving the durable triplestore:
  ~/bin/oxigraph serve --location ~/triplestore --bind 127.0.0.1:7878 &
  cd ~/rdip-sre
  OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT=7878 \
      ~/envs/sraf/bin/python -m build_harness.rescore
Then re-run analysis/summarize_results and analysis/predictor_analysis.
"""
from __future__ import annotations
import glob
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import time                                            # noqa: E402
from dashboard.fair_r_scorer import compute_fair_r   # noqa: E402
from triplestore_client import graph_exists, sparql_query  # noqa: E402
from config import OUTPUT_DIR, OXIGRAPH_URL           # noqa: E402


def graph_uri(study_id: str) -> str:
    return f"https://w3id.org/rdip/graph/{study_id}"


def _wait_for_oxigraph(timeout: int = 20) -> bool:
    for _ in range(timeout):
        try:
            sparql_query("ASK {}")
            return True
        except Exception:  # noqa: BLE001
            time.sleep(1)
    return False


def main():
    if not _wait_for_oxigraph():
        print(f"Oxigraph not reachable at {OXIGRAPH_URL}. "
              f"Start it first:  ~/bin/oxigraph serve --location ~/triplestore "
              f"--bind 127.0.0.1:7878 &")
        return

    results_dir = Path(OUTPUT_DIR)
    files = sorted(glob.glob(str(results_dir / "*.json")))
    if not files:
        print(f"No result JSONs in {results_dir}")
        return
    print(f"Re-scoring {len(files)} studies against {OXIGRAPH_URL} ...")

    updated = skipped = 0
    for f in files:
        rec = json.load(open(f))
        sid = rec.get("study_id")
        if not sid:
            continue
        if not graph_exists(graph_uri(sid)):
            print(f"  {sid:16s} no graph — skipped")
            skipped += 1
            continue

        res = compute_fair_r(sid)
        print(f"  {sid:16s} {res['total_score']:5.1f}/100  {res['tier']}")
        rec["fair_r"] = {
            "total_score": res["total_score"],
            "tier": res["tier"],
            "dimension_scores": {k: v["score"]
                                 for k, v in res["dimension_scores"].items()},
            "recommendations": res["recommendations"],
        }
        rec["fair_r_scorer"] = "graded-v2"   # provenance: which scorer produced it
        Path(f).write_text(json.dumps(rec, indent=2))
        updated += 1

    print(f"\nRe-scored {updated} studies, skipped {skipped} (no graph in store).")
    print("Next: re-run analysis/summarize_results and analysis/predictor_analysis.")


if __name__ == "__main__":
    main()
