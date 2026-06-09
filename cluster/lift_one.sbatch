#!/usr/bin/env bash
#SBATCH --job-name=sraf-lift-one
#SBATCH --output=logs/lift_one-%j.out
#SBATCH --error=logs/lift_one-%j.out
#SBATCH --partition=cpu          # EDIT-ME: CPU partition (no GPU needed — lifter only)
#SBATCH --account=REPLACE_ME     # EDIT-ME: your Slurm account
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#
# FIRST END-TO-END CLUSTER VERIFICATION.
# Mirrors the local Block 1 test: lift one repo's env files into Oxigraph and
# confirm RDIP triples land in a named graph. No LLM, no GPU.
#
# Flow:
#   1. clone a test repo to node-local scratch (shallow)
#   2. start Oxigraph as a background service bound to the durable triplestore
#   3. run the lifter against it
#   4. dump the named graph to ~/triplestore exports, then tear down
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGES="${HOME}/images"
TRIPLESTORE="${HOME}/triplestore"
SCRATCH="/tmp/${SLURM_JOB_ID:-manual}"
STUDY_ID="cluster_smoketest"
mkdir -p "${TRIPLESTORE}" "${SCRATCH}" logs

# --- 1. shallow-clone a known repo (transformers has a Dockerfile subdir) ---
CLONE="${SCRATCH}/transformers"
echo "==> Cloning test repo to scratch: ${CLONE}"
git clone --depth 1 https://github.com/huggingface/transformers.git "${CLONE}"
# Block 1 verified this exact subdir (Dockerfile present at root of it):
REPO_DIR_IN_CTR="/scratch_repo/docker/transformers-pytorch-gpu"

# --- 2. start Oxigraph as a background service on 127.0.0.1:7878 ---
echo "==> Starting Oxigraph"
apptainer run --bind "${TRIPLESTORE}:/data" "${IMAGES}/oxigraph.sif" \
    serve --location /data --bind 127.0.0.1:7878 &
OXI_PID=$!
trap 'kill ${OXI_PID} 2>/dev/null || true' EXIT

# wait for the port (bash /dev/tcp — no curl dependency on the host)
echo "==> Waiting for Oxigraph to accept connections"
for i in $(seq 1 30); do
  if (exec 3<>/dev/tcp/127.0.0.1/7878) 2>/dev/null; then echo "  up"; break; fi
  sleep 1
  [ "$i" -eq 30 ] && { echo "Oxigraph did not start"; exit 1; }
done

# --- 3. run the lifter inside the engine container (shares host network) ---
echo "==> Lifting ${STUDY_ID}"
apptainer exec \
    --bind "${REPO_ROOT}:/workspace" \
    --bind "${CLONE}:/scratch_repo" \
    --env OXIGRAPH_HOST=127.0.0.1 --env OXIGRAPH_PORT=7878 \
    "${IMAGES}/sraf-engine.sif" \
    python lifter/lifter.py \
        --study-id "${STUDY_ID}" \
        --repo-dir "${REPO_DIR_IN_CTR}" \
        --skip-ontology-check --overwrite

# --- 4. export the named graph for durable record, then tear down ---
GRAPH_URI="https://w3id.org/rdip/graph/${STUDY_ID}"
OUT="${TRIPLESTORE}/exports"; mkdir -p "${OUT}"
echo "==> Exporting <${GRAPH_URI}> to ${OUT}/${STUDY_ID}.ttl"
curl -s -H 'Accept: text/turtle' \
    "http://127.0.0.1:7878/store?graph=${GRAPH_URI}" \
    -o "${OUT}/${STUDY_ID}.ttl" || echo "  (export via curl failed — non-fatal)"

echo "==> Triples exported:"
grep -c 'rdip:' "${OUT}/${STUDY_ID}.ttl" 2>/dev/null || echo "  (none / file empty)"
echo "==> SUCCESS if the lifter logged 'Uploaded N triples'. Cluster path proven."
