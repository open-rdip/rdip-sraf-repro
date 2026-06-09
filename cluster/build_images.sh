#!/usr/bin/env bash
# Build / pull the three Apptainer images SRAF needs on the cluster.
#
#   sraf-engine.sif  — built from containers/sraf-engine.def (the pipeline)
#   oxigraph.sif     — pulled from the official Oxigraph image (triplestore)
#   vllm.sif         — pulled from vllm/vllm-openai (LLM server)
#
# Images are built in node-local scratch then moved to ~/images to avoid
# hammering the NFS home volume during the build.
#
# Usage:  bash cluster/build_images.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGES_DIR="${HOME}/images"
# Use a job-local scratch dir if inside Slurm, else a tmp dir.
SCRATCH="${SLURM_JOB_ID:+/tmp/${SLURM_JOB_ID}}"
SCRATCH="${SCRATCH:-$(mktemp -d)}"
mkdir -p "${IMAGES_DIR}" "${SCRATCH}"

# Apptainer needs a cache/tmp with room — point it at scratch, not home.
export APPTAINER_CACHEDIR="${SCRATCH}/apptainer_cache"
export APPTAINER_TMPDIR="${SCRATCH}/apptainer_tmp"
mkdir -p "${APPTAINER_CACHEDIR}" "${APPTAINER_TMPDIR}"

echo "==> Building sraf-engine.sif from def file"
apptainer build "${SCRATCH}/sraf-engine.sif" "${REPO_ROOT}/containers/sraf-engine.def"
mv -f "${SCRATCH}/sraf-engine.sif" "${IMAGES_DIR}/sraf-engine.sif"

echo "==> Pulling oxigraph.sif"
apptainer pull --force "${SCRATCH}/oxigraph.sif" docker://ghcr.io/oxigraph/oxigraph:latest
mv -f "${SCRATCH}/oxigraph.sif" "${IMAGES_DIR}/oxigraph.sif"

echo "==> Pulling vllm.sif (large — CUDA image)"
# Pin a version in production; latest is fine for first onboarding.
apptainer pull --force "${SCRATCH}/vllm.sif" docker://vllm/vllm-openai:latest
mv -f "${SCRATCH}/vllm.sif" "${IMAGES_DIR}/vllm.sif"

echo
echo "==> Done. Images in ${IMAGES_DIR}:"
ls -lh "${IMAGES_DIR}"/*.sif
