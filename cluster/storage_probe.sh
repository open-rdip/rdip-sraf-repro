#!/usr/bin/env bash
# storage_probe.sh — answer two questions before paying for 50 GB.
#
#   1. Is /tmp on a compute node its own filesystem, or is it carved out of the
#      quota that the 50 GB applies to?
#   2. How much headroom is actually left once the open-weight checkpoints go?
#
# Run it ON A COMPUTE NODE, not the login node. The login node's /tmp is often
# a different filesystem from a compute node's, and the compute node is where
# run_result.sbatch builds its venvs.
#
#   unset SBATCH_ACCOUNT
#   srun --partition=ASL-cpu --ntasks=1 --cpus-per-task=1 --mem=2G \
#        --time=00:10:00 bash cluster/storage_probe.sh
#
# Writes a 512 MB file to /tmp and deletes it. Nothing else is touched.
set -uo pipefail

USER="${USER:-$(id -un)}"

PROBE_MB="${PROBE_MB:-512}"
TMPROOT="${TMPROOT:-/tmp}"
PROBE="$TMPROOT/.storage_probe.$$"
line() { printf '\n== %s\n' "$1"; }

cleanup() { rm -f "$PROBE" 2>/dev/null; }
trap cleanup EXIT

printf 'host      : %s\n' "$(hostname)"
printf 'user      : %s\n' "$USER"
printf 'home      : %s\n' "$HOME"
printf 'slurm job : %s\n' "${SLURM_JOB_ID:-<not under slurm, results may mislead>}"

# ---------------------------------------------------------------- 1. same fs?
line "Is $TMPROOT the same filesystem as \$HOME?"
dev_tmp=$(stat -c '%d' "$TMPROOT" 2>/dev/null)
dev_home=$(stat -c '%d' "$HOME" 2>/dev/null)
printf '%-28s device=%-10s type=%s\n' "$TMPROOT" "${dev_tmp:-?}" "$(stat -f -c '%T' "$TMPROOT" 2>/dev/null)"
printf '%-28s device=%-10s type=%s\n' "$HOME" "${dev_home:-?}" "$(stat -f -c '%T' "$HOME" 2>/dev/null)"
if [ -n "$dev_tmp" ] && [ "$dev_tmp" = "$dev_home" ]; then
  echo "VERDICT: SAME filesystem. Scratch almost certainly counts against your quota."
else
  echo "VERDICT: DIFFERENT filesystems. Scratch is probably free, but confirm with the quota delta below."
fi

line "df for both"
df -h "$TMPROOT" "$HOME" 2>/dev/null

line "Slurm-provided scratch, if any (prefer these over /tmp when set)"
for v in SLURM_TMPDIR TMPDIR SCRATCH LOCAL_SCRATCH; do
  printf '%-16s = %s\n' "$v" "${!v:-<unset>}"
done

# ------------------------------------------------------------- 2. quota tools
quota_snapshot() {
  { quota -s 2>/dev/null; } | sed 's/^/  quota: /'
  { lfs quota -h -u "$USER" "$HOME" 2>/dev/null; } | sed 's/^/  lfs:   /'
  { beegfs-ctl --getquota --uid "$USER" 2>/dev/null; } | sed 's/^/  beegfs:/'
  { df -BM --output=used,avail "$HOME" 2>/dev/null | tail -1; } | sed 's/^/  df home: /'
  { df -BM --output=used,avail "$TMPROOT" 2>/dev/null | tail -1; } | sed 's/^/  df tmp : /'
  { du -sh "$HOME" 2>/dev/null | tail -1; } | sed 's/^/  du:    /'
}

line "Quota BEFORE writing ${PROBE_MB} MB to $TMPROOT"
quota_snapshot

line "Writing ${PROBE_MB} MB to $PROBE"
if dd if=/dev/zero of="$PROBE" bs=1M count="$PROBE_MB" status=none 2>/dev/null; then
  ls -lh "$PROBE"
  sync
else
  echo "WRITE FAILED. That itself is an answer: this node cannot write to $TMPROOT."
fi

line "Quota AFTER"
quota_snapshot
echo
echo "Compare the two blocks. If 'used' rose by about ${PROBE_MB} MB, scratch is"
echo "inside your quota and the 26-study reproduction has to be sized for it."

# ------------------------------------------------- 3. what is on the quota now
line "Biggest things under \$HOME right now"
du -sh "$HOME"/* 2>/dev/null | sort -rh | head -15

line "The open-weight checkpoints"
if [ -d "$HOME/models" ]; then
  du -sh "$HOME/models" 2>/dev/null
  du -sh "$HOME"/models/* 2>/dev/null | sort -rh
  echo "Deleting these frees that much. cluster/download_models.sbatch re-fetches them."
else
  echo "\$HOME/models does not exist. Nothing to reclaim there."
fi

line "Python environments"
du -sh "$HOME"/envs/* 2>/dev/null | sort -rh

line "Done"
echo "Remember the headline: the three checkpoints are about 48 GB, and N3 does"
echo "not need them. It runs on ASL-cpu against hosted APIs with no GPU."
