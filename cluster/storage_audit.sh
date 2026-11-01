#!/usr/bin/env bash
# storage_audit.sh — survey the cluster home, prove what is safely backed up,
# and print a reclaim plan. READ ONLY. It deletes nothing.
#
#   bash cluster/storage_audit.sh              # survey + backup proof + plan
#   TARGET_GB=100 bash cluster/storage_audit.sh
#
# Run it on the login node. Deletion commands are printed at the end for you to
# copy; nothing is removed by this script.
set -uo pipefail

USER="${USER:-$(id -un)}"
REPO="${REPO:-$HOME/rdip-sraf-repro}"
TARGET_GB="${TARGET_GB:-100}"
line() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
gb()   { awk -v k="${1:-0}" 'BEGIN{printf "%.1f", k/1048576}'; }   # KiB -> GiB
kib()  { du -sk "$1" 2>/dev/null | cut -f1; }

printf 'host   : %s\n' "$(hostname)"
printf 'user   : %s\n' "$USER"
printf 'repo   : %s\n' "$REPO"
printf 'target : under %s GB\n' "$TARGET_GB"

# ---------------------------------------------------------------- 1. how much
line "Where you stand"
quota -s 2>/dev/null | sed 's/^/  quota : /'
lfs quota -h -u "$USER" "$HOME" 2>/dev/null | sed 's/^/  lfs   : /'
beegfs-ctl --getquota --uid "$USER" 2>/dev/null | sed 's/^/  beegfs: /'
df -h "$HOME" 2>/dev/null | tail -1 | sed 's/^/  df    : /'
HOME_K=$(kib "$HOME")
printf '  du    : %s GB in %s\n' "$(gb "$HOME_K")" "$HOME"

# ---------------------------------------------------------------- 2. where
line "Biggest things in \$HOME"
du -sh "$HOME"/* "$HOME"/.[!.]* 2>/dev/null | sort -rh | head -20

line "Biggest things inside the repository"
[ -d "$REPO" ] && du -sh "$REPO"/* 2>/dev/null | sort -rh | head -15 \
  || echo "  repository not found at $REPO, set REPO=..."

# ------------------------------------------------- 3. is the repo safe to trim
line "Is the repository fully backed up?"
SAFE=yes
if [ -d "$REPO/.git" ]; then
  cd "$REPO" || exit 1
  BR=$(git branch --show-current)
  git fetch --quiet 2>/dev/null || echo "  (fetch failed, the ahead/behind count below may be stale)"

  MOD=$(git status --porcelain=v1 | grep -c '^ *[MDR]' || true)
  AHEAD=$(git rev-list --count "origin/$BR..HEAD" 2>/dev/null || echo '?')
  printf '  branch              : %s\n' "$BR"
  printf '  tracked but changed : %s   (must be 0)\n' "$MOD"
  printf '  commits not pushed  : %s   (must be 0)\n' "$AHEAD"
  [ "$MOD" != "0" ] && SAFE=no
  [ "$AHEAD" != "0" ] && SAFE=no

  echo
  echo "  Untracked files that git is NOT ignoring. These exist nowhere else:"
  git ls-files --others --exclude-standard | head -40 | sed 's/^/    /'
  N_UNTRACKED=$(git ls-files --others --exclude-standard | wc -l)
  printf '    ... %s file(s) in total\n' "$N_UNTRACKED"
  [ "$N_UNTRACKED" != "0" ] && SAFE=no

  echo
  echo "  Expensive outputs, confirmed tracked (so they survive a reclone):"
  for d in data/extractions data/ground_truth data/recipes validation/results \
           validation/repo_facts result_repro/results analysis; do
    printf '    %-26s %s tracked\n' "$d" "$(git ls-files "$d" 2>/dev/null | wc -l)"
  done
else
  echo "  no .git at $REPO"; SAFE=no
fi

# ---------------------------------------------------------------- 4. the plan
line "Reclaim plan, largest first"
printf '  %-34s %8s  %s\n' "candidate" "GB" "how you get it back"
TOTAL=0
cand() {   # cand <path> <how to restore>
  local p="$1" how="$2" k
  [ -e "$p" ] || return 0
  k=$(kib "$p"); TOTAL=$((TOTAL + k))
  printf '  %-34s %8s  %s\n' "${p/#$HOME/~}" "$(gb "$k")" "$how"
}
cand "$HOME/models"                  "cluster/download_models.sbatch re-fetches"
cand "$HOME/envs/vllm"               "pip install -r requirements-engine.txt"
cand "$REPO/.embeddings_cache"       "rebuilt on the next retrieval run"
cand "$REPO/test_repos"              "cloned on demand"
cand "$REPO/phase4_validation/repos" "cloned on demand"
cand "$REPO/logs"                    "disposable"
cand "$REPO/data/papers"             "re-download from paper_url_pdf in dataset_b_validation.json"
cand "$REPO/triplestore"             "rebuilt by the lifter; also on Zenodo 10.5281/zenodo.19919042"
for f in "$REPO"/*.sif "$HOME"/*.sif; do
  cand "$f" "cluster/build_images.sh rebuilds"
done
echo
printf '  %-34s %8s\n' "TOTAL RECLAIMABLE" "$(gb "$TOTAL")"
printf '  %-34s %8s\n' "you are at" "$(gb "$HOME_K")"
printf '  %-34s %8s\n' "you would land at" "$(gb $((HOME_K - TOTAL)))"
printf '  %-34s %8s\n' "target" "$TARGET_GB"

# ---------------------------------------------------------------- 5. verdict
line "Verdict"
if [ "$SAFE" = yes ]; then
  echo "  The repository is clean and pushed. Everything in the plan above is"
  echo "  either regenerable or archived, so deleting it loses no evidence."
else
  echo "  DO NOT DELETE YET. Something above is not backed up: either a tracked"
  echo "  file is modified, commits are unpushed, or untracked files exist that"
  echo "  git is not ignoring. Resolve those first, then run this again."
fi

line "Deletion commands, for you to run deliberately"
cat <<'EOS'
  # Always dry-run first. This prints what would go and the size.
  for p in ~/models ~/envs/vllm ~/rdip-sraf-repro/.embeddings_cache \
           ~/rdip-sraf-repro/test_repos ~/rdip-sraf-repro/logs; do
    [ -e "$p" ] && du -sh "$p"
  done

  # Then, one at a time, biggest first. Check the quota between each.
  rm -rf ~/models                       && df -h ~ | tail -1
  rm -rf ~/envs/vllm                    && df -h ~ | tail -1
  rm -rf ~/rdip-sraf-repro/.embeddings_cache
  rm -rf ~/rdip-sraf-repro/test_repos ~/rdip-sraf-repro/logs
  find ~/rdip-sraf-repro -name '__pycache__' -type d -prune -exec rm -rf {} +
EOS
