#!/usr/bin/env bash
#SBATCH --job-name=sraf-dl-models
#SBATCH --output=logs/download_models-%j.out
#SBATCH --error=logs/download_models-%j.out
#SBATCH --partition=ASL-cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#
# Cache the three open-weights models (8-bit / INT8) into HF_HOME so every
# later job loads them from local disk, never re-downloading.
# Containerless: uses the conda env's python (huggingface_hub ships with it
# via datasets/sentence-transformers in requirements.txt).
#
# Storage target: ~48 GB total in ~/models. Verify with `du -sh ~/models`
# afterwards — it MUST stay well under the 200 GB budget.
set -uo pipefail

export HF_HOME="${HOME}/models"
mkdir -p "${HF_HOME}" "${SLURM_SUBMIT_DIR:-.}/logs"
CONDA_PY="${HOME}/envs/sraf/bin/python"

# ----------------------------------------------------------------------------
# INT8 (w8a8 / GPTQ-Int8) checkpoints: vLLM-native, Ampere-safe (A6000),
# and true 8-bit on disk. VERIFY each repo ID still resolves before running
# (quantizer orgs move repos, e.g. neuralmagic -> RedHatAI). Llama/Mistral are
# gated — export HF_TOKEN in your shell / .env first.
# ----------------------------------------------------------------------------
MODELS=(
  "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8"                       # primary   ~15 GB
  "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"        # secondary ~9  GB
  "RedHatAI/Mistral-Small-24B-Instruct-2501-quantized.w8a8"   # third     ~24 GB
)

# The home volume was cut from 200 GB to 100 GB, so all three (~48 GB) no
# longer fit alongside everything else. Pass KEY to fetch exactly one, which
# is what the sequential grounded run needs:
#   sbatch --export=ALL,HF_TOKEN=$HF_TOKEN,KEY=llama cluster/download_models.sbatch
# Without KEY the original behaviour is unchanged: fetch all three.
if [ -n "${KEY:-}" ]; then
  ONE="$(PYTHONPATH="${SLURM_SUBMIT_DIR:-.}" "${CONDA_PY}" -c \
    "from rag_pipeline.model_registry import REGISTRY; import sys
k=sys.argv[1]
s=REGISTRY.get(k)
assert s is not None, f'unknown key {k}; known: {sorted(REGISTRY)}'
print(s.model)" "$KEY")" || { echo "could not resolve KEY=$KEY"; exit 1; }
  MODELS=("$ONE")
  echo "==> KEY=$KEY, fetching only $ONE"
fi

echo "==> free space before: $(df -h "$HOME" | awk 'NR==2{print $4}')"
export HF_TOKEN="${HF_TOKEN:-}"

for repo in "${MODELS[@]}"; do
  echo "==> Downloading ${repo}"
  HF_HOME="${HF_HOME}" "${CONDA_PY}" -c \
    "from huggingface_hub import snapshot_download; snapshot_download('${repo}', resume_download=True)"
done

echo
echo "==> Model cache size:"
du -sh "${HF_HOME}"
du -sh "${HF_HOME}"/hub/models--* 2>/dev/null || true
