#!/usr/bin/env bash
#SBATCH --job-name=sraf-grounded
#SBATCH --output=logs/grounded-%j.out
#SBATCH --error=logs/grounded-%j.out
#SBATCH --partition=ASL-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#
# Span-grounded extraction pilot with a LOCAL open-weight model (paper_notes AE).
# Twelve gold studies rather than the full corpus, so this is hours not a day.
#
# Run once per model (vLLM serves one model per server):
#   sbatch --export=ALL,HF_TOKEN=$HF_TOKEN,KEY=llama   cluster/grounded_openweight.sbatch
#   sbatch --export=ALL,HF_TOKEN=$HF_TOKEN,KEY=mistral cluster/grounded_openweight.sbatch
#   sbatch --export=ALL,HF_TOKEN=$HF_TOKEN,KEY=qwen    cluster/grounded_openweight.sbatch
#
# Smoke test first:  add ,SRAF_LIMIT=2   (two studies, proves the whole path)
#
# Home is a 100 GB volume and the three checkpoints are ~48 GB together, so
# they cannot all be resident. Add ,PURGE=1 to delete this model from HF_HOME
# after a SUCCESSFUL run, which makes the three submissions self-managing:
#   sbatch --export=ALL,HF_TOKEN=$HF_TOKEN,KEY=llama,PURGE=1 ...
# PURGE never fires on a failed run, so a crashed job leaves the weights in
# place for a retry rather than forcing a re-download.
#
# KEY is the model_registry handle, not the HF repo id. The HF id is resolved
# from the registry below so there is one source of truth for which checkpoint
# a given key means, and so the output slug matches the ungrounded corpus pass
# already on disk (tests/test_grounded.py pins this).
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}"
KEY="${KEY:?set KEY=qwen|llama|mistral}"
CONDA_PY="$HOME/envs/sraf/bin/python"
VLLM_PY="$HOME/envs/vllm/bin/python"
OXI_BIN="$HOME/bin/oxigraph"
TRIPLESTORE="$HOME/triplestore"
export HF_HOME="$HOME/models"
export HF_TOKEN="${HF_TOKEN:-}"
VPORT=8000; OPORT=7878
mkdir -p "$REPO_ROOT/logs" "$TRIPLESTORE"
cd "$REPO_ROOT"

# --- 0. resolve the checkpoint from the registry -----------------------------
MODEL="$(PYTHONPATH="$REPO_ROOT" "$CONDA_PY" -c \
  "from rag_pipeline.model_registry import REGISTRY; import sys;
k=sys.argv[1]
s=REGISTRY.get(k)
assert s is not None, f'unknown key {k}; known: {sorted(REGISTRY)}'
assert s.backend=='vllm', f'{k} is backend {s.backend}, not a local model'
print(s.model)" "$KEY")" || { echo "could not resolve KEY=$KEY"; exit 1; }
echo "==> KEY=$KEY  ->  $MODEL"

# --- 1. vLLM OpenAI server on the GPU (background) ---------------------------
EXTRA_ARGS=""
case "$MODEL" in *[Mm]istral*) EXTRA_ARGS="--tokenizer-mode mistral" ;; esac
echo "==> starting vLLM for $MODEL  ${EXTRA_ARGS}"
HF_HOME="$HF_HOME" HF_TOKEN="$HF_TOKEN" \
    "$VLLM_PY" -m vllm.entrypoints.openai.api_server \
        --model "$MODEL" --host 127.0.0.1 --port "$VPORT" \
        --max-model-len 8192 --gpu-memory-utilization 0.90 ${EXTRA_ARGS} \
    > "$REPO_ROOT/logs/vllm-$SLURM_JOB_ID.out" 2>&1 &
VLLM_PID=$!

# --- 2. Oxigraph ------------------------------------------------------------
# The grounded pilot never writes triples, but it imports rag_pipeline.pipeline
# for RETRIEVAL_QUERIES and download_pdf, which pulls in the triplestore client.
# Nothing connects at import time, so this is belt and braces rather than a
# requirement. Cheap enough to keep; removes a whole class of surprise.
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
  [ "$i" -eq 120 ] && { echo "vLLM not ready after 10 min - see logs/vllm-$SLURM_JOB_ID.out"; exit 1; }
done

# --- 3. the grounded pilot ---------------------------------------------------
LIMIT_ARG=""
[ -n "${SRAF_LIMIT:-}" ] && LIMIT_ARG="--limit $SRAF_LIMIT"

LLM_BACKEND=vllm LLM_MODEL="$MODEL" \
  VLLM_SERVER_URL="http://127.0.0.1:$VPORT" \
  OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT="$OPORT" PYTHONPATH="$REPO_ROOT" \
  "$CONDA_PY" -m rag_pipeline.grounded --models "$KEY" --tier gold $LIMIT_ARG

STATUS=$?

if [ "$STATUS" -ne 0 ]; then
  echo "==> grounded pilot FAILED for $KEY ($MODEL), exit $STATUS"
  echo "==> weights left in place for a retry; PURGE skipped"
  exit "$STATUS"
fi

echo "==> grounded pilot complete for $KEY ($MODEL)"
echo "==> outputs: $(ls -1 data/extractions_grounded/*__*.json 2>/dev/null | wc -l) files total"

# --- 4. optional purge, only on success -------------------------------------
if [ "${PURGE:-0}" = "1" ]; then
  # HF stores a repo as $HF_HOME/hub/models--<org>--<name>.
  CACHE_DIR="$HF_HOME/hub/models--$(echo "$MODEL" | sed 's#/#--#g')"
  if [ -d "$CACHE_DIR" ]; then
    SZ="$(du -sh "$CACHE_DIR" 2>/dev/null | cut -f1)"
    echo "==> PURGE=1, removing $CACHE_DIR ($SZ)"
    rm -rf "$CACHE_DIR"
    echo "==> home now: $(du -sh "$HOME" 2>/dev/null | cut -f1)"
  else
    echo "==> PURGE=1 but $CACHE_DIR not found, nothing removed"
  fi
fi
