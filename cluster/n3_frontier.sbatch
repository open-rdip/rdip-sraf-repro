#!/usr/bin/env bash
#SBATCH --job-name=sraf-n3
#SBATCH --output=logs/n3-%j.out
#SBATCH --error=logs/n3-%j.out
#SBATCH --partition=ASL-cpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#
# Contribution N3: the frontier-model sweep and the robustness re-run.
#
# No GPU. Every model in this sweep is a hosted API, so the accelerators stay
# free and this runs on ASL-cpu.
#
# Prerequisites
#   1. .env carries OPENAI_API_KEY, GOOGLE_API_KEY, XAI_API_KEY,
#      ANTHROPIC_API_KEY. Keys live there, never in this file.
#   2. ~/envs/sraf has openai, google-generativeai and anthropic installed.
#   3. Do NOT set --account: ASL runs no accounting database and any account
#      name fails the job with InvalidAccount. `unset SBATCH_ACCOUNT` first.
#
# Run the preflight interactively before submitting anything. It costs a
# fraction of a cent and catches a wrong model id, which is the failure that
# otherwise surfaces hundreds of paid calls into a pass:
#
#   python -m rag_pipeline.n3_preflight
#
# Then smoke-test three studies on one model before committing the budget:
#
#   sbatch --export=ALL,SRAF_N3_MODELS=grok,SRAF_N3_LIMIT=3 cluster/n3_frontier.sbatch
#
# Then the full plan:
#
#   sbatch --export=ALL cluster/n3_frontier.sbatch
#
# Resume is per (study, model), so a re-submission skips completed work. The
# spend cap is enforced after every completion and persists across jobs, so a
# resumed run continues counting rather than starting the budget over.
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}"
CONDA_PY="$HOME/envs/sraf/bin/python"
OXI_BIN="$HOME/bin/oxigraph"
TRIPLESTORE="$HOME/triplestore"
OPORT=7878

MODELS="${SRAF_N3_MODELS:-}"          # empty means the whole registry
LIMIT="${SRAF_N3_LIMIT:-0}"

mkdir -p "$REPO_ROOT/logs" "$TRIPLESTORE"

if [ -f "$REPO_ROOT/.env" ]; then
  set -a; . "$REPO_ROOT/.env"; set +a
fi

cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT"

# Fail before the queue slot is spent rather than after.
echo "==> preflight"
"$CONDA_PY" -m rag_pipeline.n3_preflight ${MODELS:+--models "$MODELS"} || {
  echo "preflight failed — not starting the sweep"; exit 1; }

# --- Oxigraph on the durable store (background) ---
"$OXI_BIN" serve --location "$TRIPLESTORE" --bind "127.0.0.1:$OPORT" &
OXI_PID=$!
trap 'kill $OXI_PID 2>/dev/null || true' EXIT

for i in $(seq 1 30); do
  (exec 3<>/dev/tcp/127.0.0.1/$OPORT) 2>/dev/null && break; sleep 1
  [ "$i" -eq 30 ] && { echo "Oxigraph failed to start"; exit 1; }
done
echo "==> Oxigraph up"

OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT="$OPORT" \
  "$CONDA_PY" -m rag_pipeline.run_n3_frontier \
    ${MODELS:+--models "$MODELS"} \
    ${LIMIT:+--limit "$LIMIT"}
RC=$?

echo "==> N3 finished with code $RC"
exit $RC
