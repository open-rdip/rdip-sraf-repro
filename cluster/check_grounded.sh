#!/usr/bin/env bash
# Morning report for the grounded pilot. Read-only.
#   bash cluster/check_grounded.sh
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$HOME/rdip-sraf-repro}" || exit 1
PY="$HOME/envs/sraf/bin/python"

echo "=== files per model ==="
ls data/extractions_grounded/ 2>/dev/null | sed 's/.*__//;s/\.json//' | sort | uniq -c

echo
echo "=== any job failures ==="
sacct --starttime=now-24hours --format=JobID%14,JobName%22,State%14,Elapsed 2>/dev/null \
  | grep -Ei "sraf|dl-|grounded" | grep -vi "\.batch|\.extern" || echo "  sacct unavailable"

echo
echo "=== parse failures and empty studies ==="
PYTHONPATH=. "$PY" - <<'PY'
import json, glob, os, collections
bad = []
for f in sorted(glob.glob("data/extractions_grounded/*.json")):
    d = json.load(open(f))
    nf = len(d.get("failures") or [])
    n = d["summary"]["total"].get("n", 0)
    if nf or n == 0:
        bad.append((os.path.basename(f), nf, n))
print(f"  {len(bad)} file(s) with parse failures or zero items")
for b in bad[:15]:
    print(f"    {b[0]:<62} failures={b[1]} items={b[2]}")
PY

echo
echo "=== headline ==="
PYTHONPATH=. "$PY" - <<'PY'
import json, glob, collections
NAMES = {"gpt-5":"GPT-5","gemini-3-8-flash":"Gemini","grok-4-7":"Grok",
         "claude-sonnet-5-5":"Sonnet","claude-opus-5-5":"Opus",
         "qwen-qwen2-5-14b-instruct-gptq-int8":"Qwen",
         "redhatai-meta-llama-3-1-8b-instruct-quantized-w8a8":"Llama",
         "redhatai-mistral-small-24b-instruct-2501-quantized-w8a8":"Mistral"}

def bucket(r):
    if r.get("span_loose"):               return "whitespace"
    if "fuzzy_token_recall" not in r:     return "unscored"
    if r.get("fuzzy_longest", 0) >= 0.60: return "near-verbatim"
    return "paraphrase" if r.get("fuzzy_token_recall", 0) >= 0.70 else "UNSUPPORTED"

print(f"  {'model':<9}{'files':>6}{'items':>7}{'evid':>7}{'strict':>8}{'+ws':>7}"
      f"{'wspc':>6}{'near':>6}{'para':>6}{'UNSUP':>7}{'unsc':>6}")
for slug, name in NAMES.items():
    fs = glob.glob(f"data/extractions_grounded/*__{slug}.json")
    if not fs: continue
    recs = []
    for f in fs: recs += json.load(open(f))["records"]
    n = len(recs) or 1
    ev = sum(r["has_evidence"] for r in recs)
    sp = sum(r["span_found"] for r in recs)
    aw = sum(r["span_found"] or r.get("span_loose") for r in recs)
    b = collections.Counter(bucket(r) for r in recs
                            if not r["span_found"] and r["has_evidence"])
    print(f"  {name:<9}{len(fs):>6}{len(recs):>7}{100*ev/n:>6.0f}%{100*sp/n:>7.0f}%"
          f"{100*aw/n:>6.0f}%{b['whitespace']:>6}{b['near-verbatim']:>6}"
          f"{b['paraphrase']:>6}{b['UNSUPPORTED']:>7}{b['unscored']:>6}")

# the question the Llama run exists to answer
print("\n  === seeds claimed with verifiable evidence (N3 ungrounded: Llama 52/95) ===")
for slug, name in NAMES.items():
    fs = glob.glob(f"data/extractions_grounded/*__{slug}.json")
    if not fs: continue
    seeds = [r for f in fs for r in json.load(open(f))["records"]
             if r["field"] == "random_seeds"]
    ok = sum(r["span_found"] or r.get("span_loose") for r in seeds)
    studies = {f for f in fs if any(r["field"] == "random_seeds"
               for r in json.load(open(f))["records"])}
    print(f"    {name:<9} {len(seeds):>3} seed items, {ok:>3} evidenced, "
          f"in {len(studies)}/{len(fs)} studies")
PY

echo
echo "=== token accounting (open-weight gap being filled) ==="
[ -f data/usage/cluster/usage.json ] && "$PY" -m json.tool data/usage/cluster/usage.json | head -40 \
  || echo "  no data/usage/cluster/usage.json yet"
