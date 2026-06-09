#!/usr/bin/env bash
#SBATCH --job-name=sraf-dl-models
#SBATCH --output=logs/download_models-%j.out
#SBATCH --error=logs/download_models-%j.out
#SBATCH --partition=cpu          # EDIT-ME: CPU partition (download is not GPU work)
#SBATCH --account=REPLACE_ME     # EDIT-ME: your Slurm account
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#
# Cache the three open-weights models (8-bit / INT8) into HF_HOME so every
# later job loads them from local disk, never re-downloading.
#
# Storage target: ~48 GB total in ~/models. Verify with `du -sh ~/models`
# after this finishes — it MUST stay well under the 200 GB budget.
set -euo pipefail

export HF_HOME="${HOME}/models"
mkdir -p "${HF_HOME}" logs
ENGINE_IMG="${HOME}/images/sraf-engine.sif"

# ----------------------------------------------------------------------------
# Model list — INT8 (w8a8 / GPTQ-Int8) checkpoints: vLLM-native, Ampere-safe,
# and small on disk (true 8-bit weights, not fp16-then-quantize).
#
# !!! VERIFY each repo ID still exists and matches the current HF org before
#     the first run (orgs occasionally move, e.g. neuralmagic -> RedHatAI). !!!
# ----------------------------------------------------------------------------
MODELS=(
  "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8"                       # primary   ~15 GB
  "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"        # secondary ~9  GB
  "RedHatAI/Mistral-Small-Instruct-2409-quantized.w8a8"       # third     ~23 GB
)

# huggingface_hub ships with the engine image (via datasets/sentence-transformers).
# If a model is gated (Llama/Mistral), export HF_TOKEN in your .env / shell first.
export HF_TOKEN="${HF_TOKEN:-}"

for repo in "${MODELS[@]}"; do
  echo "==> Downloading ${repo}"
  apptainer exec --bind "${HF_HOME}:${HF_HOME}" --env HF_HOME="${HF_HOME}" \
      --env HF_TOKEN="${HF_TOKEN}" "${ENGINE_IMG}" \
      python -c "from huggingface_hub import snapshot_download; \
                 snapshot_download('${repo}', resume_download=True)"
done

echo
echo "==> Model cache size:"
du -sh "${HF_HOME}"
echo "==> Per-model:"
du -sh "${HF_HOME}"/hub/models--* 2>/dev/null || true
