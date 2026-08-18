#!/usr/bin/env bash
#SBATCH --job-name=sraf-repro-run
#SBATCH --output=logs/repro-run-%j.out
#SBATCH --error=logs/repro-run-%j.out
#SBATCH --partition=ASL-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=1-00:00:00
#
# PHASE 2 of result-level reproduction: run each runnable repo's experiment and
# compare to the paper's claimed number. NO vLLM here — the whole GPU goes to the
# repo experiments (a 24B server + an experiment do not fit on one 48 GB card).
# Recipes must already exist (run extract_recipes.sbatch first); metrics are read
# from the log with the regex parser (--no-llm-parse). Streaming + resumable.
#
#   sbatch result_repro/extract_recipes.sbatch    # phase 1 (once)
#   sbatch result_repro/run_all.sbatch            # phase 2
#   # smoke-test one:  sbatch --export=ALL,STUDY=study002 result_repro/run_all.sbatch
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sre}"; cd "$REPO_ROOT"; mkdir -p logs
CONDA_PY="$HOME/envs/sraf/bin/python"

STUDY_ARG=""; [ -n "${STUDY:-}" ] && STUDY_ARG="--study ${STUDY}"
FORCE_ARG=""; [ -n "${FORCE:-}" ] && FORCE_ARG="--force"
"$CONDA_PY" -m result_repro.run_all \
    --no-llm-parse ${STUDY_ARG} ${FORCE_ARG} \
    --run-timeout "${RUN_TIMEOUT:-2700}" \
    --disk-cap "${DISK_CAP:-40}"

echo "==> done. results in result_repro/results/summary.{json,csv}"
