#!/usr/bin/env bash
#SBATCH --job-name=sraf-repro-all
#SBATCH --output=logs/repro-all-%j.out
#SBATCH --error=logs/repro-all-%j.out
#SBATCH --partition=ASL-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=1-00:00:00
#
# End-to-end, engine-driven result-level reproduction over all runnable studies.
# Serves a local vLLM (for recipe extraction + reading metrics off logs), then runs
# result_repro.run_all, which streams each repo (clone -> recipe -> run -> compare ->
# delete) and writes only result_repro/results/summary.{json,csv}. Resumable.
#
#   sbatch result_repro/run_all.sbatch
#
# NOTE on GPU sharing: vLLM holds the model in GPU memory (~24 GB for the 24B int8)
# while each repo's experiment also uses the GPU. A 48 GB card usually fits an
# eval-from-checkpoint run alongside it; if you hit OOM on a specific repo, either
# use a smaller vLLM model or run with --no-llm-parse (regex metric parse) and a
# separate recipe-extraction pass beforehand.
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sre}"
cd "$REPO_ROOT"
mkdir -p logs

CONDA_PY="$HOME/envs/sraf/bin/python"
VLLM_PY="$HOME/envs/vllm/bin/python"
# HF repo id served by vLLM (resolved from the local HF cache). Best extractor:
MODEL="${MODEL:-RedHatAI/Mistral-Small-24B-Instruct-2501-quantized.w8a8}"
PORT="${PORT:-8000}"

# Mistral models need vLLM's mistral tokenizer mode; others don't.
EXTRA_ARGS=""
case "$MODEL" in *[Mm]istral*) EXTRA_ARGS="--tokenizer-mode mistral" ;; esac

# --- serve vLLM (background) ---
echo "==> starting vLLM: $MODEL  ${EXTRA_ARGS}"
"$VLLM_PY" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" --host 127.0.0.1 --port "$PORT" \
    --max-model-len 8192 --gpu-memory-utilization 0.55 ${EXTRA_ARGS} &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null' EXIT

echo "==> waiting for vLLM to come up ..."
for i in $(seq 1 120); do
  curl -s "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1 && { echo "   up"; break; }
  sleep 5
done

# --- run the sweep (engine-driven, streaming, resumable) ---
# smoke-test one repo:  sbatch --export=ALL,STUDY=study002 result_repro/run_all.sbatch
export VLLM_SERVER_URL="http://127.0.0.1:${PORT}"
STUDY_ARG=""; [ -n "${STUDY:-}" ] && STUDY_ARG="--study ${STUDY}"
"$CONDA_PY" -m result_repro.run_all \
    --backend vllm --model "$MODEL" ${STUDY_ARG} \
    --run-timeout "${RUN_TIMEOUT:-2700}" \
    --disk-cap "${DISK_CAP:-40}"

echo "==> done. results in result_repro/results/summary.{json,csv}"
