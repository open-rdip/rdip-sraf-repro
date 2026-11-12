#!/usr/bin/env bash
#
# A/B the pooled extraction against the Mistral-only baseline, cleanly.
#
#   bash cluster/ab_pool_compare.sh backups/graphs_20261112T081515Z
#
# Why a script rather than steps in a terminal: the manual version of this has
# already gone wrong twice today. `verify --restore` run as a second command
# restored the pooled graph instead of the original, and a rescore was run
# without first capturing the baseline. Both were instruction errors, and both
# are the kind a script does not make.
#
# A = Mistral only          (restored from the snapshot)
# B = Mistral + Grok + GPT-5 + Sonnet
#
# Ends with the store in state B, which is what the paper will report, and with
# both sets of outputs saved side by side under analysis/ab/.
set -uo pipefail

SNAP="${1:?usage: ab_pool_compare.sh <snapshot dir>}"
cd "${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}" || exit 1
PY="$HOME/envs/sraf/bin/python"
export OXIGRAPH_HOST="${OXIGRAPH_HOST:-127.0.0.1}" OXIGRAPH_PORT="${OXIGRAPH_PORT:-7878}"
export PYTHONPATH="$PWD"
OUT=analysis/ab
mkdir -p "$OUT"

[ -f "$SNAP/MANIFEST.json" ] || { echo "not a snapshot: $SNAP"; exit 1; }
curl -sf "http://$OXIGRAPH_HOST:$OXIGRAPH_PORT/query?query=ASK%7B%7D" >/dev/null \
  || { echo "oxigraph not reachable at $OXIGRAPH_HOST:$OXIGRAPH_PORT"; exit 1; }

run_state () {                      # $1 = A|B, $2 = label
  echo "=== scoring state $1 ($2) ==="
  "$PY" -m build_harness.rescore          > "$OUT/fairr_$1.txt"   2>&1
  "$PY" -m analysis.predictor_analysis    > "$OUT/predictor_$1.md" 2>&1
  cp analysis/predictor_table.csv "$OUT/predictor_table_$1.csv" 2>/dev/null
  grep -cE "^  (study|ref)" "$OUT/fairr_$1.txt" | xargs echo "  scored:"
}

echo "=== A: restoring all graphs to Mistral-only from $SNAP ==="
"$PY" -m analysis.pool_extractors restore --snapshot "$SNAP" | tail -3
run_state A "Mistral only"

echo
echo "=== B: pooling Grok + GPT-5 + Sonnet back in ==="
"$PY" -m analysis.pool_extractors pool --snapshot "$SNAP" | tail -6
run_state B "pooled, 4 extractors"

echo
echo "=== FAIR-R: which studies moved? ==="
"$PY" - <<'PYEOF'
import re
def scores(p):
    out = {}
    for line in open(p, encoding="utf-8"):
        m = re.match(r"\s+((?:study|ref)\d+)\s+([\d.]+)/100", line)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out
a, b = scores("analysis/ab/fairr_A.txt"), scores("analysis/ab/fairr_B.txt")
keys = sorted(set(a) & set(b))
moved = [(k, a[k], b[k]) for k in keys if abs(a[k] - b[k]) > 1e-9]
print(f"  {len(keys)} studies compared, {len(moved)} moved, "
      f"{len(keys) - len(moved)} unchanged")
if keys:
    print(f"  mean change: {sum(b[k] - a[k] for k in keys) / len(keys):+.2f} points")
for k, x, y in sorted(moved, key=lambda t: -(t[2] - t[1])):
    print(f"    {k}  {x:5.1f} -> {y:5.1f}   {y - x:+.1f}")
PYEOF

echo
echo "=== predictor analysis: A vs B ==="
diff -u analysis/ab/predictor_A.md analysis/ab/predictor_B.md \
  && echo "  (identical)"

cat <<EOF

=== done ===
  store is now in state B (pooled), which is what the paper reports.
  outputs:
    $OUT/fairr_A.txt        $OUT/fairr_B.txt
    $OUT/predictor_A.md     $OUT/predictor_B.md
    $OUT/predictor_table_A.csv  $OUT/predictor_table_B.csv
  to go back to A:  $PY -m analysis.pool_extractors restore --snapshot $SNAP
EOF
