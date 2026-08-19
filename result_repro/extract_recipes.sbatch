#!/usr/bin/env bash
#SBATCH --job-name=sraf-recipes
#SBATCH --output=logs/recipes-%j.out
#SBATCH --error=logs/recipes-%j.out
#SBATCH --partition=ASL-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#
# PHASE 1 of result-level reproduction: engine extracts the execution recipe for
# every runnable study. vLLM gets the whole GPU here (0.90), like the corpus
# extraction job — no repo experiments run in this phase, so there is no GPU
# contention. Writes data/recipes/<study>.json.
#
#   sbatch result_repro/extract_recipes.sbatch
#   # then phase 2:  sbatch result_repro/run_all.sbatch
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sre}"; cd "$REPO_ROOT"; mkdir -p logs
CONDA_PY="$HOME/envs/sraf/bin/python"
VLLM_PY="$HOME/envs/vllm/bin/python"
MODEL="${MODEL:-RedHatAI/Mistral-Small-24B-Instruct-2501-quantized.w8a8}"
PORT="${PORT:-8000}"

EXTRA_ARGS=""
case "$MODEL" in *[Mm]istral*) EXTRA_ARGS="--tokenizer-mode mistral" ;; esac

echo "==> starting vLLM: $MODEL  ${EXTRA_ARGS}"
"$VLLM_PY" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" --host 127.0.0.1 --port "$PORT" \
    --max-model-len 8192 --gpu-memory-utilization 0.90 ${EXTRA_ARGS} &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null' EXIT

echo "==> waiting for vLLM to load (24B — can take several minutes) ..."
up=0
for i in $(seq 1 240); do
  curl -sf "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1 && { up=1; echo "   vLLM up"; break; }
  sleep 10
done
[ "$up" = "1" ] || { echo "vLLM failed to come up in 40 min"; exit 1; }

export VLLM_SERVER_URL="http://127.0.0.1:${PORT}"
export LLM_MAX_TOKENS="${LLM_MAX_TOKENS:-3000}"   # avoid truncating longer recipes (e.g. study019)
STUDY_ARG=""; [ -n "${STUDY:-}" ] && STUDY_ARG="--study ${STUDY}"
"$CONDA_PY" -m result_repro.extract_recipes \
    --backend vllm --model "$MODEL" ${STUDY_ARG}

echo "==> recipes written to data/recipes/ — now run phase 2 (run_all.sbatch)"
