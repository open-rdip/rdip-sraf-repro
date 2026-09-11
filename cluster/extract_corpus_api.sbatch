#!/usr/bin/env bash
#SBATCH --job-name=sraf-extract-api
#SBATCH --output=logs/extract-api-%j.out
#SBATCH --error=logs/extract-api-%j.out
#SBATCH --partition=ASL-cpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#
# Phase II extraction against HOSTED API models (WS3 / journal item 3).
#
# Unlike cluster/extract_corpus.sbatch this needs NO GPU: there is no local
# model to serve, so it runs on ASL-cpu and leaves the A6000s free. Because
# SRAF_MODELS multiplexing works for API backends, every API model runs in ONE
# submission (vLLM still needs one submission per model — it serves one model
# per server).
#
# Prerequisites
#   1. .env (or the environment) carries OPENAI_API_KEY / GOOGLE_API_KEY.
#   2. ~/envs/sraf has the `openai` (and, for gemini, `google-generativeai`)
#      client installed.
#   3. Do NOT set --account: ASL runs no accounting database and any account
#      name fails the job with InvalidAccount. `unset SBATCH_ACCOUNT` if your
#      shell exports one.
#
# Submit:
#   sbatch --export=ALL,SRAF_MODELS="openai:gpt-4o,google:gemini-1.5-pro" \
#          cluster/extract_corpus_api.sbatch
#
# Smoke test three studies first — do this before spending the budget:
#   sbatch --export=ALL,SRAF_LIMIT=3,SRAF_MODELS="openai:gpt-4o" \
#          cluster/extract_corpus_api.sbatch
#
# Resume is per-(study, model), so a re-submission skips completed work and
# graphs are model-scoped, so models never collide.
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}"
CONDA_PY="$HOME/envs/sraf/bin/python"
OXI_BIN="$HOME/bin/oxigraph"
TRIPLESTORE="$HOME/triplestore"
OPORT=7878

: "${SRAF_MODELS:?set SRAF_MODELS=\"backend:model,backend:model\" (e.g. openai:gpt-4o)}"
mkdir -p "$REPO_ROOT/logs" "$TRIPLESTORE"

# Load .env if present (keys live there, never in the sbatch file).
if [ -f "$REPO_ROOT/.env" ]; then
  set -a; . "$REPO_ROOT/.env"; set +a
fi

# Fail early and loudly rather than burning a queue slot on a missing key.
case "$SRAF_MODELS" in
  *openai:*) [ -n "${OPENAI_API_KEY:-}" ] || { echo "OPENAI_API_KEY not set"; exit 1; } ;;
esac
case "$SRAF_MODELS" in
  *google:*|*gemini:*) [ -n "${GOOGLE_API_KEY:-}" ] || { echo "GOOGLE_API_KEY not set"; exit 1; } ;;
esac

# Reachability check — compute nodes do have outbound HTTPS (verified 2026-09-11,
# api.openai.com returns 401). A hard failure here means a network change.
curl -sf -o /dev/null --max-time 20 https://api.openai.com/v1/models \
  || echo "WARN: api.openai.com not reachable without auth (401 is expected and fine)"

# --- Oxigraph on the durable store (background) ---
"$OXI_BIN" serve --location "$TRIPLESTORE" --bind "127.0.0.1:$OPORT" &
OXI_PID=$!
trap 'kill $OXI_PID 2>/dev/null || true' EXIT

for i in $(seq 1 30); do
  (exec 3<>/dev/tcp/127.0.0.1/$OPORT) 2>/dev/null && break; sleep 1
  [ "$i" -eq 30 ] && { echo "Oxigraph failed to start"; exit 1; }
done
echo "==> Oxigraph up; running models: $SRAF_MODELS"

cd "$REPO_ROOT"
SRAF_MODELS="$SRAF_MODELS" \
  OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT="$OPORT" PYTHONPATH="$REPO_ROOT" \
  "$CONDA_PY" -m rag_pipeline.run_corpus_extraction

echo "==> API extraction complete for: $SRAF_MODELS"
