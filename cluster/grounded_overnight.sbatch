#!/usr/bin/env bash
#SBATCH --job-name=sraf-grounded-night
#SBATCH --output=logs/grounded-night-%j.out
#SBATCH --error=logs/grounded-night-%j.out
#SBATCH --partition=ASL-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=10:00:00
#
# Both open-weight models in ONE job. Use this instead of
# cluster/run_openweight_chain.sh when only a single job may be submitted or
# queued at a time.
#
#   sbatch --export=ALL,HF_TOKEN=$HF_TOKEN cluster/grounded_overnight.sbatch
#
# Sequential by necessity: vLLM serves one model per server, and home is 100 GB
# so the checkpoints cannot coexist. Each model is downloaded, served, run, and
# then deleted before the next begins. The GPU is held during the downloads,
# which is wasteful but keeps everything inside one allocation.
#
# No Oxigraph here. The grounded path imports rag_pipeline.retrieval rather
# than rag_pipeline.pipeline, so nothing touches the triplestore.
set -uo pipefail

REPO="${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}"
cd "$REPO" || exit 1
PY="$HOME/envs/sraf/bin/python"
VLLM_PY="$HOME/envs/vllm/bin/python"
export HF_HOME="$HOME/models"
export HF_TOKEN="${HF_TOKEN:-}"
export SRAF_USAGE_DIR="$REPO/data/usage/cluster"
export PYTHONPATH="$REPO"
VPORT=8000
mkdir -p logs "$SRAF_USAGE_DIR" "$HF_HOME"

free_gb() { df -BG --output=avail "$HOME" 2>/dev/null | tail -1 | tr -dc '0-9'; }
stamp()   { date '+%H:%M:%S'; }

echo "==> start $(date). home free: $(free_gb) GB"
[ -n "$HF_TOKEN" ] || echo "!! HF_TOKEN empty; gated repos (Llama) will fail"

run_one() {
  local KEY="$1"
  echo
  echo "############ $(stamp)  $KEY ############"

  local MODEL
  MODEL="$("$PY" -c "
from rag_pipeline.model_registry import REGISTRY
import sys
s = REGISTRY[sys.argv[1]]
assert s.backend == 'vllm', s.backend
print(s.model)" "$KEY")" || { echo "!! cannot resolve $KEY"; return 1; }
  echo "==> $KEY -> $MODEL"

  # --- download ---
  echo "==> $(stamp) fetching weights (free: $(free_gb) GB)"
  HF_HOME="$HF_HOME" HF_TOKEN="$HF_TOKEN" "$PY" -c "
from huggingface_hub import snapshot_download
snapshot_download('$MODEL', resume_download=True)" || { echo "!! download failed for $KEY"; return 1; }
  echo "==> $(stamp) fetched. free: $(free_gb) GB"

  # --- serve ---
  local EXTRA=""
  case "$MODEL" in *[Mm]istral*) EXTRA="--tokenizer-mode mistral" ;; esac
  echo "==> $(stamp) starting vLLM $EXTRA"
  HF_HOME="$HF_HOME" HF_TOKEN="$HF_TOKEN" \
    "$VLLM_PY" -m vllm.entrypoints.openai.api_server \
      --model "$MODEL" --host 127.0.0.1 --port "$VPORT" \
      --max-model-len 8192 --gpu-memory-utilization 0.90 ${EXTRA} \
    > "logs/vllm-$KEY-$SLURM_JOB_ID.out" 2>&1 &
  local VPID=$!

  local up=0
  for i in $(seq 1 120); do
    curl -sf "http://127.0.0.1:$VPORT/v1/models" >/dev/null 2>&1 && { up=1; break; }
    kill -0 "$VPID" 2>/dev/null || { echo "!! vLLM died, see logs/vllm-$KEY-$SLURM_JOB_ID.out"; break; }
    sleep 5
  done
  [ "$up" -eq 1 ] || { echo "!! vLLM never came up for $KEY"; kill "$VPID" 2>/dev/null; return 1; }
  echo "==> $(stamp) vLLM up"

  # --- run ---
  LLM_BACKEND=vllm LLM_MODEL="$MODEL" VLLM_SERVER_URL="http://127.0.0.1:$VPORT" \
    "$PY" -m rag_pipeline.grounded --models "$KEY" --tier gold
  local STATUS=$?
  echo "==> $(stamp) grounded exit $STATUS"

  kill "$VPID" 2>/dev/null; wait "$VPID" 2>/dev/null

  # --- purge, success only ---
  if [ "$STATUS" -eq 0 ]; then
    local DIR="$HF_HOME/hub/models--$(echo "$MODEL" | sed 's#/#--#g')"
    [ -d "$DIR" ] && { echo "==> purging $DIR"; rm -rf "$DIR"; }
    echo "==> free after purge: $(free_gb) GB"
  else
    echo "!! $KEY failed, weights kept for retry"
  fi
  return "$STATUS"
}

# Llama first: it carries the seed question. Qwen runs even if Llama fails,
# because the two are independent and a wasted night is worse than a partial one.
run_one llama; LLAMA=$?
run_one qwen;  QWEN=$?

echo
echo "############ done $(date) ############"
echo "  llama exit $LLAMA   qwen exit $QWEN   home free $(free_gb) GB"
ls data/extractions_grounded/ | sed 's/.*__//;s/\.json//' | sort | uniq -c
echo
echo "  next: bash cluster/check_grounded.sh"
[ "$LLAMA" -eq 0 ] && [ "$QWEN" -eq 0 ]
