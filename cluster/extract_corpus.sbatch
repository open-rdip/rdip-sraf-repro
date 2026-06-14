#!/usr/bin/env bash
#SBATCH --job-name=sraf-extract
#SBATCH --output=logs/extract-%j.out
#SBATCH --error=logs/extract-%j.out
#SBATCH --partition=ASL-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=1-00:00:00
#
# Phase II extraction. Cluster policy = 1 running job, so vLLM (GPU, in the
# Apptainer container) and Oxigraph and the extraction loop all run in THIS one
# job. Run once per model:
#   sbatch --export=ALL,HF_TOKEN=$HF_TOKEN,MODEL=Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8 \
#          cluster/extract_corpus.sbatch
# Smoke test first:  add ,SRAF_LIMIT=3
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sre}"
MODEL="${MODEL:?set MODEL=<hf repo id>}"
CONDA_PY="$HOME/envs/sraf/bin/python"
OXI_BIN="$HOME/bin/oxigraph"
VLLM_IMG="$HOME/images/vllm.sif"
TRIPLESTORE="$HOME/triplestore"
export HF_HOME="$HOME/models"
export HF_TOKEN="${HF_TOKEN:-}"
VPORT=8000; OPORT=7878
mkdir -p "$REPO_ROOT/logs" "$TRIPLESTORE"

# --- 1. vLLM OpenAI server on the GPU (background) ---
# Mistral models need vLLM's mistral tokenizer mode; others don't.
EXTRA_ARGS=""
case "$MODEL" in *[Mm]istral*) EXTRA_ARGS="--tokenizer-mode mistral" ;; esac
echo "==> starting vLLM for $MODEL  ${EXTRA_ARGS}"
apptainer exec --nv \
    --bind "$HF_HOME:$HF_HOME" \
    --env HF_HOME="$HF_HOME" --env HF_TOKEN="$HF_TOKEN" \
    "$VLLM_IMG" python3 -m vllm.entrypoints.openai.api_server \
        --model "$MODEL" --host 127.0.0.1 --port "$VPORT" \
        --max-model-len 8192 --gpu-memory-utilization 0.90 ${EXTRA_ARGS} \
    > "$REPO_ROOT/logs/vllm-$SLURM_JOB_ID.out" 2>&1 &
VLLM_PID=$!

# --- 2. Oxigraph on the durable store (background) ---
"$OXI_BIN" serve --location "$TRIPLESTORE" --bind "127.0.0.1:$OPORT" &
OXI_PID=$!
trap 'kill $VLLM_PID $OXI_PID 2>/dev/null || true' EXIT

for i in $(seq 1 30); do
  (exec 3<>/dev/tcp/127.0.0.1/$OPORT) 2>/dev/null && break; sleep 1
  [ "$i" -eq 30 ] && { echo "Oxigraph failed to start"; exit 1; }
done

echo "==> waiting for vLLM to load $MODEL (can take several minutes) ..."
for i in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$VPORT/v1/models" >/dev/null 2>&1 && { echo "  vLLM up"; break; }
  sleep 5
  [ "$i" -eq 120 ] && { echo "vLLM not ready after 10 min — see logs/vllm-$SLURM_JOB_ID.out"; exit 1; }
done

# --- 3. extraction loop (conda env hits the vLLM API over localhost) ---
cd "$REPO_ROOT"
LLM_BACKEND=vllm LLM_MODEL="$MODEL" \
  VLLM_SERVER_URL="http://127.0.0.1:$VPORT" \
  OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT="$OPORT" PYTHONPATH="$REPO_ROOT" \
  "$CONDA_PY" -m rag_pipeline.run_corpus_extraction

echo "==> extraction complete for $MODEL"
