#!/usr/bin/env bash
# Assemble the Apptainer images SRAF needs on the cluster.
#
# IMPORTANT — fakeroot constraint on AIT Slurm:
#   This account is NOT in /etc/subuid and user-namespace mapping is disabled,
#   so `apptainer build` from a .def file FAILS (it can't run the %post section).
#   Workaround: pull prebuilt images (no %post) and convert a Docker-built
#   engine image. Neither path needs fakeroot.
#
#   ENGINE: build it with Docker on your Mac, then ship the tar here:
#     # on Mac:
#     docker build --platform=linux/amd64 \
#         -f containers/sraf-engine.Dockerfile -t sraf-engine:latest .
#     docker save sraf-engine:latest | gzip > ~/sraf-engine.tar.gz
#     scp ~/sraf-engine.tar.gz dsai-st125286p@ait-slurm:~/
#     # on cluster:
#     gunzip ~/sraf-engine.tar.gz
#   ...then run this script.
#
# Usage:  bash cluster/build_images.sh
set -euo pipefail

IMAGES_DIR="${HOME}/images"
ENGINE_TAR="${HOME}/sraf-engine.tar"
mkdir -p "${IMAGES_DIR}"

# --- engine: convert the Docker archive shipped from the Mac (no fakeroot) ---
if [[ -f "${ENGINE_TAR}" ]]; then
  echo "==> Converting engine docker-archive -> sraf-engine.sif"
  apptainer build --force "${IMAGES_DIR}/sraf-engine.sif" "docker-archive:${ENGINE_TAR}"
else
  echo "!! ${ENGINE_TAR} not found."
  echo "   Build sraf-engine:latest with Docker on your Mac, docker save it,"
  echo "   scp the tar here, gunzip it, then re-run. Skipping engine for now."
fi

# --- oxigraph: pull (no %post, works unprivileged) ---
echo "==> Pulling oxigraph.sif"
apptainer pull --force "${IMAGES_DIR}/oxigraph.sif" docker://ghcr.io/oxigraph/oxigraph:latest

# --- vllm: large CUDA image — only needed for RAG / the build harness, ---
# --- NOT for the lifter-only verification. Uncomment when wiring up vLLM. ---
# echo "==> Pulling vllm.sif"
# apptainer pull --force "${IMAGES_DIR}/vllm.sif" docker://vllm/vllm-openai:latest

echo
echo "==> Images in ${IMAGES_DIR}:"
ls -lh "${IMAGES_DIR}"/*.sif 2>/dev/null || echo "  (none yet)"
