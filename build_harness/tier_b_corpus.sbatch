#!/usr/bin/env bash
#SBATCH --job-name=sraf-tierb
#SBATCH --output=logs/tierb-%A_%a.out
#SBATCH --error=logs/tierb-%A_%a.out
#SBATCH --partition=ASL-cpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --array=1-96%8
#
# Tier-B static checks over the 96-repository corpus.
#
# Arrays ARE available on ASL (MaxArraySize=1001, no accounting database and so
# no per-user job limits) — the single-sequential-job design recorded in the old
# notes was self-imposed. But ASL-cpu is ONE node (128 CPUs, ~123 GB) shared
# with the lab and OverSubscribe=NO, so the throttle `%8` is deliberate: it
# gives real parallelism without monopolising the machine.
#
# --mem and --time are explicit because DefMemPerNode=UNLIMITED: a job that
# omits --mem asks for the whole node and pends behind everyone.
#
# Do NOT set --account (no accounting database; any account fails the job with
# InvalidAccount). `unset SBATCH_ACCOUNT` if your shell exports one.
#
# Submit:
#   sbatch build_harness/tier_b_corpus.sbatch
# Smoke test three studies first:
#   sbatch --array=1-3 build_harness/tier_b_corpus.sbatch
# Link-rot pass (separate, and record the date — liveness is time-dependent):
#   sbatch --export=ALL,TIER_B_ONLINE=1 build_harness/tier_b_corpus.sbatch
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}"
PY="$HOME/envs/sraf/bin/python"
[ -x "$PY" ] || PY=python3
cd "$REPO_ROOT" || exit 1
mkdir -p logs validation/tier_b

# Node-local scratch: clones never touch the 200 GB home volume.
export SLURM_TMPDIR="/tmp/${SLURM_JOB_ID:-local}"
mkdir -p "$SLURM_TMPDIR"
trap 'rm -rf "$SLURM_TMPDIR"' EXIT

ONLINE_FLAG=""
[ "${TIER_B_ONLINE:-0}" = "1" ] && ONLINE_FLAG="--online"

echo "==> Tier-B task ${SLURM_ARRAY_TASK_ID:-1} ${ONLINE_FLAG}"
PYTHONPATH="$REPO_ROOT" "$PY" build_harness/run_tier_b_corpus.py \
    --index "${SLURM_ARRAY_TASK_ID:-1}" $ONLINE_FLAG
echo "==> done"
