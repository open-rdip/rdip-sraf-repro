#!/usr/bin/env bash
#SBATCH --job-name=sraf-audit-one
#SBATCH --output=logs/audit-one-%j.out
#SBATCH --error=logs/audit-one-%j.out
#SBATCH --partition=ASL-cpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#
# Audit ONE external paper and repository end to end.
#
# Written for the committee request of 19 October 2026: a member sends a paper
# and its repository and wants the score. This does the whole chain in one
# submission: clone, lift the repository, Level-1 build test, retrieval
# augmented extraction from the paper, FAIR-R, and a durable result record.
#
# It needs no GPU. The extraction runs against a hosted API model, so the only
# cost is tokens, and one study is a few cents.
#
# Prerequisites
#   1. .env carries GOOGLE_API_KEY (or OPENAI_API_KEY, and set SRAF_BACKEND).
#   2. ~/envs/sraf has the client library and sentence-transformers.
#   3. The paper PDF is on the cluster. Copy it up first, for example:
#        scp paper.pdf <cluster>:~/rdip-sraf-repro/data/papers/study900.pdf
#   4. Do NOT set --account: ASL runs no accounting database.
#
# Submit from the repository root:
#   sbatch --export=ALL,SRAF_STUDY=study900,\
# SRAF_REPO_URL=https://github.com/xxhu94/CSGNN,\
# SRAF_PDF=data/papers/study900.pdf \
#          cluster/audit_one.sbatch
#
# Results land in:
#   validation/results/<study>.json          build outcome + FAIR-R
#   data/extractions/<study>__<model>.json   the extracted metadata
#   validation/repo_facts/<study>.json       the deterministic parse
#   $HOME/triplestore/exports/<study>.ttl    the study graph
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}"
CONDA_PY="$HOME/envs/sraf/bin/python"
OXI_BIN="$HOME/bin/oxigraph"
TRIPLESTORE="$HOME/triplestore"
OPORT=7878

: "${SRAF_STUDY:?set SRAF_STUDY, e.g. study900}"
: "${SRAF_REPO_URL:?set SRAF_REPO_URL, the git clone URL}"
: "${SRAF_PDF:?set SRAF_PDF, path to the paper PDF relative to the repo root}"
SRAF_BACKEND="${SRAF_BACKEND:-google}"
SRAF_MODEL="${SRAF_MODEL:-gemini-2.5-flash}"

cd "$REPO_ROOT"
mkdir -p logs "$TRIPLESTORE" validation/results data/extractions validation/repo_facts

echo "==> study    : $SRAF_STUDY"
echo "==> repo     : $SRAF_REPO_URL"
echo "==> paper    : $SRAF_PDF"
echo "==> extractor: $SRAF_BACKEND:$SRAF_MODEL"

[ -f "$SRAF_PDF" ] || { echo "PDF not found at $SRAF_PDF"; exit 1; }

# --- Oxigraph on the durable store -------------------------------------------
"$OXI_BIN" serve --location "$TRIPLESTORE" --bind "127.0.0.1:$OPORT" &
OXI_PID=$!
trap 'kill $OXI_PID 2>/dev/null || true' EXIT
for i in $(seq 1 30); do
  (exec 3<>/dev/tcp/127.0.0.1/$OPORT) 2>/dev/null && { echo "==> oxigraph up"; break; }
  sleep 1
  [ "$i" -eq 30 ] && { echo "Oxigraph failed to start"; exit 1; }
done

export OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT="$OPORT" PYTHONPATH="$REPO_ROOT"

# --- 1. repository side: clone, lift, build test, first FAIR-R ----------------
echo "==> [1/4] repository: clone, lift, build test"
"$CONDA_PY" -m build_harness.process_repo \
    --study-id "$SRAF_STUDY" --repo-url "$SRAF_REPO_URL" --keep \
  || echo "    process_repo returned non-zero, continuing"

# --- 2. deterministic fact parse ---------------------------------------------
echo "==> [2/4] deterministic repository facts"
CLONE="${SRAF_SCRATCH_DIR:-/tmp/sraf}/$SRAF_STUDY"
"$CONDA_PY" - "$CLONE" "$SRAF_STUDY" <<'PY'
import sys, json, pathlib
from build_harness.repo_facts import extract_repo_facts
clone, study = sys.argv[1], sys.argv[2]
if pathlib.Path(clone).exists():
    f = extract_repo_facts(clone)
    pathlib.Path("validation/repo_facts").mkdir(parents=True, exist_ok=True)
    pathlib.Path(f"validation/repo_facts/{study}.json").write_text(json.dumps(f, indent=2))
    print(f"    files read {f.get('n_files_read')}  "
          f"datasets {len(f.get('datasets') or [])}  "
          f"hyperparams {len(f.get('hyperparameters') or [])}  "
          f"seeds {len(f.get('seeds') or [])}  "
          f"metrics {len(f.get('metrics') or [])}")
else:
    print(f"    clone not found at {clone}; skipping")
PY

# --- 3. paper side: retrieval augmented extraction ----------------------------
echo "==> [3/4] paper: retrieval augmented extraction"
"$CONDA_PY" - "$SRAF_STUDY" "$SRAF_PDF" "$SRAF_BACKEND" "$SRAF_MODEL" <<'PY'
import sys, json
from rag_pipeline.pipeline import run
study, pdf, backend, model = sys.argv[1:5]
res = run(study_id=study, pdf_path=pdf, backend=backend, model=model, save_json=True)
print("   ", json.dumps(res))
PY

# --- 4. re-score with the paper side present, then export --------------------
echo "==> [4/4] FAIR-R over the merged graph, and export"
"$CONDA_PY" - "$SRAF_STUDY" <<'PY'
import sys, json, pathlib
from dashboard.fair_r_scorer import compute_fair_r, score_summary
study = sys.argv[1]
try:
    r = compute_fair_r(study, verbose=True)
    print(score_summary(r))
    p = pathlib.Path(f"validation/results/{study}.json")
    rec = json.loads(p.read_text()) if p.exists() else {"study_id": study}
    rec["fair_r"] = r
    p.write_text(json.dumps(rec, indent=2))
    print(f"    wrote {p}")
except Exception as e:
    print(f"    FAIR-R failed: {type(e).__name__}: {e}")
PY

GRAPH="https://w3id.org/rdip/graph/${SRAF_STUDY}"
OUT="$TRIPLESTORE/exports"; mkdir -p "$OUT"
curl -s -G "http://127.0.0.1:$OPORT/store" \
     --data-urlencode "graph=$GRAPH" -H 'Accept: text/turtle' \
     -o "$OUT/${SRAF_STUDY}.ttl" && echo "==> exported $OUT/${SRAF_STUDY}.ttl"

echo "==> done. Collect:"
echo "    validation/results/${SRAF_STUDY}.json"
echo "    data/extractions/${SRAF_STUDY}__*.json"
echo "    validation/repo_facts/${SRAF_STUDY}.json"
echo "    $OUT/${SRAF_STUDY}.ttl"
