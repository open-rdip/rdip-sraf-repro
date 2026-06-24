#!/usr/bin/env bash
#SBATCH --job-name=sraf-result
#SBATCH --output=logs/result-%j.out
#SBATCH --error=logs/result-%j.out
#SBATCH --partition=ASL-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=1-00:00:00
#
# Result-reproducibility runner (RQ #20) — execute ONE full-tier repo's
# experiment and capture its output so you can read off the obtained metric.
#
#   sbatch --export=ALL,STUDY=study003 result_repro/run_result.sbatch
#
# Reads repo_url + run.command from result_repro/manifest.yaml for STUDY, clones
# the repo, builds a venv on its declared Python, runs the command, and tees all
# output to logs/result-<job>.out. Then read the metric from the log and fill
# `obtained:` for that study in the manifest, and set its `status`.
#
# NOTE: datasets are NOT auto-staged. Set run.data_ready=true in the manifest
# only after the repo's data is in place (per its README).
set -uo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$HOME/rdip-sre}"
STUDY="${STUDY:?set STUDY=studyNNN}"
CONDA_PY="$HOME/envs/sraf/bin/python"
MANIFEST="$REPO_ROOT/result_repro/manifest.yaml"
SCRATCH="/tmp/result-$SLURM_JOB_ID"
mkdir -p "$REPO_ROOT/logs" "$SCRATCH"
trap 'rm -rf "$SCRATCH"' EXIT

# --- pull repo_url + command for this study out of the manifest ---
read -r REPO_URL CMD < <("$CONDA_PY" - "$MANIFEST" "$STUDY" <<'PY'
import sys, yaml
man = yaml.safe_load(open(sys.argv[1])) or []
e = next((m for m in man if m["study_id"] == sys.argv[2]), None)
if not e:
    print("NONE NONE"); sys.exit()
cmd = (e.get("run") or {}).get("command") or ""
print(e.get("repo_url") or "NONE", cmd.replace("\n", " ") or "NONE")
PY
)
echo "==> STUDY=$STUDY  repo=$REPO_URL"
[ "$REPO_URL" = "NONE" ] && { echo "no repo_url in manifest"; exit 1; }
[ "$CMD" = "NONE" ] && { echo "run.command is empty in manifest — fill it first"; exit 1; }

# --- clone + environment (declared Python ladder, like the build harness) ---
git clone --depth 1 "$REPO_URL" "$SCRATCH/repo" || { echo "clone failed"; exit 1; }
cd "$SCRATCH/repo"
PYV="$REPO_ROOT/.python-version"; PYBIN="python3"
for cand in "$HOME/pys/py310/bin/python" "$HOME/pys/py39/bin/python" python3; do
  [ -x "$cand" ] && { PYBIN="$cand"; break; }
done
"$PYBIN" -m venv .venv && source .venv/bin/activate
python -m pip install -q --upgrade pip
[ -f requirements.txt ] && pip install -q -r requirements.txt || true
[ -f setup.py ] && pip install -q -e . || true

# --- run the experiment ---
echo "==> running: $CMD"
echo "================= EXPERIMENT OUTPUT ================="
eval "$CMD" 2>&1 || echo "   (command exited non-zero)"
echo "================= END OUTPUT ================="
echo "==> done $STUDY — read the metric above and fill obtained[] in the manifest"
