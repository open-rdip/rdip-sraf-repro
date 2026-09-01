#!/usr/bin/env bash
#SBATCH --job-name=sraf-corpus
#SBATCH --output=logs/corpus-%j.out
#SBATCH --error=logs/corpus-%j.out
#SBATCH --partition=ASL-cpu
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=3-00:00:00
#
# CLUSTER POLICY: max 1 running job per user, 1 node per job, 7-day max.
# So this is a SINGLE job that processes the whole corpus SEQUENTIALLY (NOT a
# Slurm array). One Oxigraph writer for the whole run => triples land directly
# in the durable triplestore; no separate merge step needed.
#
# Resumable: repos whose results JSON already exists are skipped, so you can run
# the corpus in chunks across several submissions (set SRAF_LIMIT per run).
#
#   smoke test (3 repos):
#     sbatch --export=ALL,SRAF_LIMIT=3 build_harness/run_corpus.sbatch
#   full corpus:
#     sbatch build_harness/run_corpus.sbatch
#   re-process everything from scratch:
#     sbatch --export=ALL,SRAF_FORCE=1 build_harness/run_corpus.sbatch
set -uo pipefail   # no -e: one bad repo must not abort the whole corpus

REPO_ROOT="${SLURM_SUBMIT_DIR:-${HOME}/rdip-sre}"
CONDA_PY="${HOME}/envs/sraf/bin/python"
OXIGRAPH_BIN="${HOME}/bin/oxigraph"
REPO_LIST="${REPO_ROOT}/validation/repo_list.csv"
RESULTS_DIR="${REPO_ROOT}/validation/results"
TRIPLESTORE="${HOME}/triplestore"
EXPORT_DIR="${TRIPLESTORE}/exports"
SCRATCH="/tmp/${SLURM_JOB_ID}"
PORT=7878
LIMIT="${SRAF_LIMIT:-0}"      # 0 = process all remaining
mkdir -p "${TRIPLESTORE}" "${EXPORT_DIR}" "${SCRATCH}" "${RESULTS_DIR}" "${REPO_ROOT}/logs"

# --- single durable Oxigraph for the whole job (sequential => single writer) ---
echo "==> Starting Oxigraph on the durable store ${TRIPLESTORE}"
"${OXIGRAPH_BIN}" serve --location "${TRIPLESTORE}" --bind "127.0.0.1:${PORT}" &
OXI_PID=$!
trap 'kill ${OXI_PID} 2>/dev/null || true; rm -rf "${SCRATCH}"' EXIT
for i in $(seq 1 30); do
  (exec 3<>/dev/tcp/127.0.0.1/${PORT}) 2>/dev/null && break
  sleep 1; [ "$i" -eq 30 ] && { echo "Oxigraph failed to start"; exit 1; }
done

cd "${REPO_ROOT}"
processed=0
# Iterate corpus rows (skip header). study_id=field1, repo_url=field2.
while IFS=, read -r STUDY_ID REPO_URL _rest; do
  STUDY_ID="${STUDY_ID//$'\r'/}"; REPO_URL="${REPO_URL//$'\r'/}"
  [ -z "${STUDY_ID}" ] && continue

  if [ -f "${RESULTS_DIR}/${STUDY_ID}.json" ] && [ "${SRAF_FORCE:-0}" != "1" ]; then
    echo "==> ${STUDY_ID}: already done — skipping"; continue
  fi

  processed=$((processed + 1))
  if [ "${LIMIT}" -gt 0 ] && [ "${processed}" -gt "${LIMIT}" ]; then
    echo "==> Reached SRAF_LIMIT=${LIMIT} — stopping (resume with another submission)"
    break
  fi

  echo "==> [${processed}] ${STUDY_ID}  ${REPO_URL}"
  REPO_SCRATCH="${SCRATCH}/${STUDY_ID}"
  OXIGRAPH_HOST=127.0.0.1 OXIGRAPH_PORT="${PORT}" PYTHONPATH="${REPO_ROOT}" \
    SRAF_EXPORT_DIR="${EXPORT_DIR}" \
    "${CONDA_PY}" -m build_harness.process_repo \
        --study-id "${STUDY_ID}" --repo-url "${REPO_URL}" --scratch "${REPO_SCRATCH}" \
    || echo "   (process_repo exited non-zero for ${STUDY_ID} — continuing)"
  rm -rf "${REPO_SCRATCH}"
done < <(tail -n +2 "${REPO_LIST}")

echo "==> Corpus run complete. Processed ${processed} repo(s) this submission."
echo "==> Triples are in the durable store; results in validation/results/."
