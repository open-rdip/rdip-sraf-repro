#!/usr/bin/env bash
#SBATCH --job-name=sraf-facts
#SBATCH --output=logs/facts-%A_%a.out
#SBATCH --error=logs/facts-%A_%a.out
#SBATCH --partition=ASL-cpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --array=1-96%8
#
# Deterministic repo-side experimental facts over the 96-repository corpus:
# datasets, hyperparameters, computable metrics and seeds. This is the repository
# half of the paper-vs-repo semantic diff (contribution N4).
#
# Same shape as tier_b_corpus.sbatch, and the same constraints apply, none of
# which are guesses — each was learned the hard way on this cluster:
#
#   ASL-cpu is ONE node (128 CPUs, ~123 GB) shared with the lab, and
#   OverSubscribe=NO, so `%8` throttles concurrency to get real parallelism
#   without monopolising the machine.
#
#   DefMemPerNode=UNLIMITED, so a job that omits --mem asks for the whole node
#   and pends behind everyone. --mem and --time are explicit for that reason.
#
#   Do NOT set --account. There is no accounting database, and any account value
#   fails the job with InvalidAccount. `unset SBATCH_ACCOUNT` if your shell
#   exports one.
#
# The sweep is resumable and version-stamped: a study already written by the
# current FACTS_VERSION is skipped, one written by an older version is re-run.
# So a re-submission after a partial run costs only the skips, and a bumped
# FACTS_VERSION re-does exactly the stale records rather than the whole corpus.
#
# Submit:
#   sbatch build_harness/repo_facts_corpus.sbatch
# Smoke test three studies first:
#   sbatch --array=1-3 build_harness/repo_facts_corpus.sbatch
# Re-run one study (e.g. after a clone failure):
#   sbatch --array=12 build_harness/repo_facts_corpus.sbatch
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}"
PY="$HOME/envs/sraf/bin/python"
[ -x "$PY" ] || PY=python3
cd "$REPO_ROOT" || exit 1
mkdir -p logs validation/repo_facts

# Node-local scratch: clones never touch the 200 GB home volume, and the trap
# removes them even if the task is cancelled mid-clone.
export SLURM_TMPDIR="/tmp/${SLURM_JOB_ID:-local}"
mkdir -p "$SLURM_TMPDIR"
trap 'rm -rf "$SLURM_TMPDIR"' EXIT

echo "==> repo-facts task ${SLURM_ARRAY_TASK_ID:-1}"
PYTHONPATH="$REPO_ROOT" "$PY" build_harness/run_repo_facts_corpus.py \
    --index "${SLURM_ARRAY_TASK_ID:-1}"
echo "==> done"
