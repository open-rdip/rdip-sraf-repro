#!/usr/bin/env bash
#
# Submit the whole open-weight grounded pilot as one dependency chain, so it
# runs unattended overnight.
#
#   bash cluster/run_openweight_chain.sh
#
# Home is 100 GB and the three checkpoints are ~48 GB together, so they cannot
# all be resident. The chain is strictly sequential and each model's weights
# are deleted after its run succeeds:
#
#   [free Mistral] -> dl llama -> run llama (purge) -> dl qwen -> run qwen (purge)
#
# Every preflight check runs BEFORE anything is submitted. A chain that starts
# and then fails at 3am on a missing token has wasted the night.
set -uo pipefail

REPO="${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}"
cd "$REPO" || { echo "cannot cd to $REPO"; exit 1; }
PY="$HOME/envs/sraf/bin/python"
MISTRAL_SLUG="redhatai-mistral-small-24b-instruct-2501-quantized-w8a8"
MISTRAL_DIR="$HOME/models/hub/models--RedHatAI--Mistral-Small-24B-Instruct-2501-quantized.w8a8"
fail=0
say() { printf "  %-46s %s\n" "$1" "$2"; }

echo "=== preflight ==="

# 1. gated repos need a token, and the chain is useless without it
if [ -n "${HF_TOKEN:-}" ]; then say "HF_TOKEN" "set"
else say "HF_TOKEN" "MISSING - Llama is a gated repo"; fail=1; fi

# 2. the interpreter that actually has the dependencies
[ -x "$PY" ] && say "conda python" "$PY" || { say "conda python" "MISSING at $PY"; fail=1; }

# 3. code must be current, or the output lacks span_loose and stored passages
#    and tomorrow starts with a re-score instead of a result
for marker in "def span_found_loose" '"passages": passages'; do
  if grep -q "$marker" rag_pipeline/grounded.py 2>/dev/null; then
    say "grounded.py has: ${marker:0:28}" "ok"
  else
    say "grounded.py has: ${marker:0:28}" "STALE - git pull first"; fail=1
  fi
done
[ -f rag_pipeline/retrieval.py ] && say "rag_pipeline/retrieval.py" "present" \
  || { say "rag_pipeline/retrieval.py" "MISSING - git pull first"; fail=1; }

# 4. inputs that never arrive with a pull
say "gold PDFs + embeddings" "$(ls data/papers 2>/dev/null | wc -l) pdfs, $(ls .embeddings_cache 2>/dev/null | wc -l) cached"
for s in study001 study002 study003 study005 study006 study008 \
         study009 study013 study015 study017 study020 study022; do
  [ -e "data/papers/$s.pdf" ] || { say "missing pdf" "$s"; fail=1; }
  [ -d ".embeddings_cache/$s" ] || { say "missing embeddings" "$s"; fail=1; }
done

# 5. Mistral must be finished before its weights are freed
n_mistral=$(ls data/extractions_grounded/*__${MISTRAL_SLUG}.json 2>/dev/null | wc -l)
if [ "$n_mistral" -ge 12 ]; then say "Mistral outputs" "$n_mistral/12, safe to free weights"
else say "Mistral outputs" "only $n_mistral/12 - NOT freeing weights"; fi

# 6. room for the next download
avail=$(df -BG --output=avail "$HOME" 2>/dev/null | tail -1 | tr -dc '0-9')
say "home free" "${avail:-?} GB (Llama needs ~9, Qwen ~15)"

[ "$fail" -ne 0 ] && { echo; echo "preflight FAILED, nothing submitted."; exit 1; }

# --- free Mistral, only if its run is complete -------------------------------
if [ "$n_mistral" -ge 12 ] && [ -d "$MISTRAL_DIR" ]; then
  echo; echo "=== freeing Mistral weights ($(du -sh "$MISTRAL_DIR" | cut -f1)) ==="
  rm -rf "$MISTRAL_DIR"
  echo "  home now $(df -BG --output=avail "$HOME" | tail -1 | tr -dc '0-9') GB free"
fi

# --- the chain ---------------------------------------------------------------
# --kill-on-invalid-dep=yes: if a step fails, cancel the rest rather than leave
# jobs PENDING forever on a dependency that can never be satisfied.
echo; echo "=== submitting ==="
D="--kill-on-invalid-dep=yes"
E="ALL,HF_TOKEN=$HF_TOKEN"

j1=$(sbatch --parsable --output=logs/dl-llama-%j.out \
     --export="$E,KEY=llama" cluster/download_models.sbatch)
say "1. download llama" "job $j1"

j2=$(sbatch --parsable $D --dependency=afterok:$j1 \
     --output=logs/grounded-llama-%j.out \
     --export="$E,KEY=llama,PURGE=1" cluster/grounded_openweight.sbatch)
say "2. grounded llama (purge)" "job $j2  after $j1"

j3=$(sbatch --parsable $D --dependency=afterok:$j2 \
     --output=logs/dl-qwen-%j.out \
     --export="$E,KEY=qwen" cluster/download_models.sbatch)
say "3. download qwen" "job $j3  after $j2"

j4=$(sbatch --parsable $D --dependency=afterok:$j3 \
     --output=logs/grounded-qwen-%j.out \
     --export="$E,KEY=qwen,PURGE=1" cluster/grounded_openweight.sbatch)
say "4. grounded qwen (purge)" "job $j4  after $j3"

cat <<EOF

=== submitted: $j1 -> $j2 -> $j3 -> $j4 ===

  watch:    squeue -u \$USER
  logs:     tail -f logs/grounded-llama-*.out
  vllm:     tail -f logs/vllm-*.out
  failures: sacct -j $j1,$j2,$j3,$j4 --format=JobID,JobName%24,State,Elapsed

In the morning:
  PYTHONPATH=. $PY -m analysis.rescore_grounded --dry-run
  bash cluster/check_grounded.sh
EOF
