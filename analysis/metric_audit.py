"""Hand-audit the studies where no computable metric was detected.

49 of 96 repositories produced zero metrics. Two explanations look identical in
the coverage table and imply opposite things:

  detector_gap      the code does compute a metric, in a form the four signals
                    in repo_facts.py do not recognise. Fixable; the coverage
                    number is an underestimate.
  genuinely_absent  the repository ships no evaluation code at all. Not fixable,
                    and a finding: `metric_never_computed` is undecidable for
                    these because the evaluation is missing, not because the
                    detector is weak.

This does the mechanical half. It re-clones each sampled repository AT THE
COMMIT RECORDED IN THE SWEEP (so the audit sees exactly what the extractor saw,
not today's HEAD), runs a deliberately over-inclusive search for anything
metric-shaped, and writes a worksheet. You fill in one verdict per study.

The broad search must not reuse the strict detectors — that would find nothing
by construction and "confirm" the coverage number it is meant to test. It casts
a wide net on purpose and will produce false hits; judging them is the job.

    python3 analysis/metric_audit.py --sample 10          # build the worksheet
    python3 analysis/metric_audit.py --score              # after you fill it in
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTS_DIR = Path(os.getenv("REPO_FACTS_OUT", ROOT / "validation" / "repo_facts"))
EXTRACTIONS = ROOT / "data" / "extractions"
SHEET = ROOT / "analysis" / "metric_audit_sheet.md"

VERDICTS = ("detector_gap", "genuinely_absent", "unclear")

# Deliberately loose. Anything here is a CANDIDATE, not a detection.
BROAD = re.compile(
    r"\b(accuracy|acc|f1|precision|recall|auc|auroc|mAP|mIoU|iou|dice|psnr|ssim|"
    r"bleu|rouge|meteor|perplexity|ppl|wer|cer|rmse|mse|mae|ndcg|mrr|top-?1|top-?5|"
    r"score|metric|eval|evaluat|benchmark|validat)\w*", re.I)

EVAL_FILE = re.compile(r"(eval|test|metric|score|benchmark|valid)", re.I)
CODE_SUFFIX = (".py", ".sh", ".ipynb", ".yaml", ".yml", ".cfg", ".json", ".md")
SKIP = {".git", "node_modules", "site-packages", "third_party", "build", "dist"}


def fetch_at_commit(url: str, sha: str | None, dest: Path) -> tuple[bool, str]:
    """Check out the exact recorded commit, so the audit and the sweep agree.
    A --depth 1 clone gets today's HEAD, which may no longer be what was swept."""
    dest.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true"}
    def run(*args, **kw):
        return subprocess.run(args, capture_output=True, text=True,
                              timeout=kw.get("timeout", 300), env=env, cwd=str(dest))
    try:
        run("git", "init", "-q")
        run("git", "remote", "add", "origin", url)
        if sha:
            p = run("git", "fetch", "--depth", "1", "-q", "origin", sha)
            if p.returncode == 0:
                run("git", "checkout", "-q", "FETCH_HEAD")
                return True, sha
        p = run("git", "fetch", "--depth", "1", "-q", "origin", "HEAD")
        if p.returncode != 0:
            return False, (p.stderr or "fetch failed").strip()[:200]
        run("git", "checkout", "-q", "FETCH_HEAD")
        return True, "HEAD (recorded commit unavailable)"
    except Exception as e:                                        # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def survey(repo: Path, limit: int = 14) -> dict:
    """What a human would look for: evaluation-shaped files, and lines that
    mention anything metric-like."""
    eval_files, hits, n_code = [], [], 0
    for p in repo.rglob("*"):
        if not p.is_file() or SKIP & set(p.parts):
            continue
        if p.suffix.lower() not in CODE_SUFFIX:
            continue
        n_code += 1
        rel = p.relative_to(repo)
        if EVAL_FILE.search(p.name):
            eval_files.append(str(rel))
        if len(hits) >= limit:
            continue
        try:
            if p.stat().st_size > 300_000:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:                                         # noqa: BLE001
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if len(hits) >= limit:
                break
            if BROAD.search(line) and len(line.strip()) < 160:
                hits.append(f"{rel}:{i}: {line.strip()[:120]}")
    return {"n_code_files": n_code,
            "eval_files": sorted(eval_files)[:10],
            "candidate_lines": hits}


def paper_metrics(sid: str) -> list[str]:
    out = set()
    for p in EXTRACTIONS.glob(f"{sid}__*.json"):
        md = (json.loads(p.read_text()) or {}).get("metadata") or {}
        for e in md.get("evaluation_results") or []:
            if e.get("metric"):
                out.add(str(e["metric"]))
    return sorted(out)[:12]


def build(sample: int, seed: int) -> int:
    zero = []
    for p in sorted(FACTS_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        if d.get("status") == "ok" and not d.get("metrics"):
            zero.append(d)
    if not zero:
        print("no zero-metric studies — nothing to audit")
        return 1

    random.Random(seed).shuffle(zero)
    chosen = zero[:sample]
    print(f"{len(zero)} zero-metric studies; auditing {len(chosen)} (seed={seed})\n")

    lines = [
        "# Metric audit worksheet",
        "",
        f"Sample of {len(chosen)} from {len(zero)} studies where `repo_facts` "
        "detected no computable metric.",
        f"Selection is `random.Random({seed}).shuffle` over the sorted list, so it "
        "is reproducible and was fixed before any study was looked at.",
        "",
        "For each study, set **verdict** to one of:",
        "",
        "- `detector_gap` — the repository DOES compute a metric, in a form the "
        "four signals miss. Note how it is expressed.",
        "- `genuinely_absent` — no evaluation code. The claim cannot be checked "
        "from this artifact at all.",
        "- `unclear` — you could not tell in a couple of minutes. Say so rather "
        "than guessing; an honest `unclear` rate is itself reportable.",
        "",
        "Candidate lines below are from a deliberately loose keyword search and "
        "include false hits by design. They are a starting point, not evidence.",
        "",
        "---",
        "",
    ]
    scratch = Path(tempfile.mkdtemp(prefix="metric_audit_"))
    try:
        for i, d in enumerate(chosen, 1):
            sid, url, sha = d["study_id"], d.get("repo_url", ""), d.get("repo_commit")
            print(f"  [{i}/{len(chosen)}] {sid} …", end=" ", flush=True)
            dest = scratch / sid
            ok, note = fetch_at_commit(url, sha, dest)
            info = survey(dest) if ok else {}
            print("ok" if ok else f"FAILED ({note})")

            lines += [f"## {sid}", "",
                      f"- repo: {url}",
                      f"- commit: `{sha or 'not recorded'}`" +
                      ("" if note == sha else f"  ({note})"),
                      f"- paper claims: {', '.join(paper_metrics(sid)) or '(none extracted)'}",
                      f"- code files: {info.get('n_code_files', 'n/a')}", ""]
            if info.get("eval_files"):
                lines += ["Evaluation-shaped filenames:", "",
                          *[f"- `{f}`" for f in info["eval_files"]], ""]
            else:
                lines += ["Evaluation-shaped filenames: **none**", ""]
            if info.get("candidate_lines"):
                lines += ["Candidate lines (loose search, expect false hits):", "",
                          "```", *info["candidate_lines"], "```", ""]
            else:
                lines += ["Candidate lines: **none**", ""]
            lines += ["**verdict:** ", "", "**note:** ", "", "---", ""]
            shutil.rmtree(dest, ignore_errors=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    SHEET.parent.mkdir(parents=True, exist_ok=True)
    SHEET.write_text("\n".join(lines))
    print(f"\nwrote {SHEET}")
    print("Fill in each **verdict:** line, then: python3 analysis/metric_audit.py --score")
    return 0


def score() -> int:
    if not SHEET.exists():
        print(f"no worksheet at {SHEET} — build it first")
        return 1
    text = SHEET.read_text()
    studies = re.findall(r"^## (study\d+)", text, re.M)
    verdicts = [v.strip().strip("`") for v in
                re.findall(r"^\*\*verdict:\*\*(.*)$", text, re.M)]
    filled = [(s, v) for s, v in zip(studies, verdicts) if v]
    bad = [(s, v) for s, v in filled if v not in VERDICTS]
    if bad:
        print("unrecognised verdicts (use " + " / ".join(VERDICTS) + "):")
        for s, v in bad:
            print(f"  {s}: {v!r}")
        return 1
    if not filled:
        print("no verdicts filled in yet")
        return 1

    c = Counter(v for _, v in filled)
    n = len(filled)
    print(f"{n}/{len(studies)} studies judged\n")
    for v in VERDICTS:
        print(f"  {v:18s} {c[v]:3d}  ({100*c[v]/n:5.1f}%)")

    total_zero = sum(1 for p in FACTS_DIR.glob("*.json")
                     if not json.loads(p.read_text()).get("metrics"))
    gap = c["detector_gap"] / n
    print(f"\nExtrapolated over all {total_zero} zero-metric studies:")
    print(f"  ~{gap*total_zero:.0f} are a detector gap, "
          f"~{(1-gap)*total_zero:.0f} genuinely lack evaluation code.")
    print("\nWith n =", n, "this is indicative, not an estimate. Report the")
    print("sample size and the raw counts, not the extrapolation alone.")
    if c["unclear"]:
        print(f"\n{c['unclear']} unclear — report this rather than forcing a split.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20261231)
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    return score() if a.score else build(a.sample, a.seed)


if __name__ == "__main__":
    raise SystemExit(main())
