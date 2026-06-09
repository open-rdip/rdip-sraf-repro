#!/usr/bin/env bash
#SBATCH --job-name=sraf-corpus
#SBATCH --output=logs/corpus-%A_%a.out
#SBATCH --error=logs/corpus-%A_%a.out
#SBATCH --partition=ASL-cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#
# !!! FIRST RUN: smoke-test with a tiny array, e.g.  --array=1-3
#     THEN scale to the full corpus:                 --array=1-96%6
#     (%6 = at most 6 repos building at once)
#SBATCH --array=1-3
#
# STREAMING build harness — one repo per array task. Each task:
#   - reads its row from validation/repo_list.csv
#   - starts its OWN Oxigraph (scratch store, unique port) — no contention
#   - clones to node-local scratch, lifts, build-tests, scores
#   - exports the named graph to ~/triplestore/exports/<study>.ttl + results JSON
#   - deletes the clone (corpus never accumulates on the home volume)
#
# After the array finishes, run merge_results.py to load the .ttl exports into
# the durable triplestore.
set -uo pipefail   # NB: no -e — one bad repo must not kill the task hard

REPO_ROOT="${SLURM_SUBMIT_DIR:-${HOME}/rdip-sre}"
CONDA_PY="${HOME}/envs/sraf/bin/python"
OXIGRAPH_BIN="${HOME}/bin/oxigraph"
REPO_LIST="${REPO_ROOT}/validation/repo_list.csv"
EXPORT_DIR="${HOME}/triplestore/exports"
SCRATCH="/tmp/${SLURM_JOB_ID}"
PORT=$(( 7878 + (SLURM_ARRAY_TASK_ID % 1000) ))
mkdir -p "${SCRATCH}/oxi" "${EXPORT_DIR}" "${REPO_ROOT}/logs"

# --- read the CSV row for this task (line = task id + 1, header is line 1) ---
ROW=$(sed -n "$(( SLURM_ARRAY_TASK_ID + 1 ))p" "${REPO_LIST}")
STUDY_ID=$(echo "${ROW}" | cut -d, -f1)
REPO_URL=$(echo "${ROW}" | cut -d, -f2)
if [[ -z "${STUDY_ID}" || "${STUDY_ID}" == "study_id" ]]; then
  echo "No repo for array index ${SLURM_ARRAY_TASK_ID} — nothing to do."; exit 0
fi
echo "==> [${SLURM_ARRAY_TASK_ID}] ${STUDY_ID}  ${REPO_URL}  (oxigraph :${PORT})"

# --- per-task Oxigraph on a scratch store ---
"${OXIGRAPH_BIN}" serve --location "${SCRATCH}/oxi" --bind "127.0.0.1:${PORT}" &
OXI_PID=$!
trap 'kill ${OXI_PID} 2>/dev/null || true; rm -rf "${SCRATCH}"' EXIT
for i in $(seq 1 30); do
  if (exec 3<>/dev/tcp/127.0.0.1/${PORT}) 2>/dev/null; then break; fi
  sleep 1
  [ "$i" -eq 30 ] && { echo "Oxigraph failed to start"; exit 1; }
done

# --- process this one repo ---
cd "${REPO_ROOT}"
OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT="${PORT}" PYTHONPATH="${REPO_ROOT}" \
  SRAF_EXPORT_DIR="${EXPORT_DIR}" \
  "${CONDA_PY}" -m build_harness.process_repo \
      --study-id "${STUDY_ID}" \
      --repo-url "${REPO_URL}" \
      --scratch "${SCRATCH}"

echo "==> [${SLURM_ARRAY_TASK_ID}] done — results in validation/results/${STUDY_ID}.json"
