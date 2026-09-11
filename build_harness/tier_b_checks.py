"""Tier-B reproducibility checks: the criteria the failure taxonomy says matter.

Motivation
----------
`analysis/criterion_validity.py` showed 57.8 of FAIR-R's 100 points are identical
across all 96 repositories, and `analysis/taxonomy_restructure.py` showed that 15
of the 16 genuine artifact failures map onto criteria that are either absent from
the rubric or inside that invariant mass. This module implements the five checks
those failures actually call for.

Design constraints, all deliberate:

* **Deterministic.** No language model. Every score is a function of file
  contents, so re-running on the same commit gives the same answer. This is what
  lets the criteria be audited, unlike the LLM-extracted fields whose entity-level
  F1 is ~0.27.
* **Evidence-bearing.** Every result carries the string that produced it. A score
  a reader cannot trace is not useful in a paper about reproducibility.
* **Offline by default.** Only `links_resolve` touches the network, and it is
  skipped unless explicitly enabled, so the corpus sweep stays reproducible.

Grading matches the FAIR-R convention so the two instruments stay comparable:
    0 = absent, 1 = partial, 2 = full   (see dashboard/fair_r_scorer.LEVEL_FACTOR)

Usage:
    python3 build_harness/tier_b_checks.py <repo_dir> [--paper-title "..."] [--online]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from difflib import SequenceMatcher
from pathlib import Path

ABSENT, PARTIAL, FULL = 0, 1, 2
LEVEL_NAME = {ABSENT: "absent", PARTIAL: "partial", FULL: "full"}

DOC_NAMES = ("readme", "install", "usage", "getting_started", "reproduce",
             "reproducibility", "docs", "run", "train", "eval", "evaluation")
DOC_SUFFIXES = (".md", ".rst", ".txt", "")

# A token that means "the reader must substitute something here".
PLACEHOLDER_PATTERNS = [
    r"/path[_/]to[_/]", r"/path/to\b", r"\bpath/to/", r"\bPATH_TO\b",
    r"/path_to\b", r"\b(?:my|some|local)_?path\b",
    r"<[^>\s]{1,40}>",              # <checkpoint>, <config>
    r"\{\{?[A-Za-z_][A-Za-z0-9_]*\}?\}",   # {config}, {{ckpt}}
    r"\bYOUR_[A-Z_]+\b", r"\byour_[a-z_]+\b",
    r"\$\{?[A-Z][A-Z0-9_]{2,}\}?",  # $CONFIG, ${NGPUS} — unset shell vars
    r"\.\.\.", r"\[…\]", r"\bTODO\b", r"\bFIXME\b",
    r"\bXXX+\b", r"\bNAME_OF_[A-Z_]+\b",
]

# Commands that plausibly *run* something.
RUN_TOKEN = re.compile(
    r"^\s*(?:\$\s*)?(?:CUDA_VISIBLE_DEVICES=\S+\s+|[A-Z_]+=\S+\s+)*"
    r"(python3?|bash|sh|torchrun|accelerate|srun|make|\./\S+)\b",
    re.M)

# Commands that indicate an *evaluation / reproduction* route specifically.
EVAL_HINT = re.compile(
    r"(?<![A-Za-z])(test|eval|evaluate|evaluation|inference|predict|reproduce|"
    r"benchmark|validate|demo)(?![A-Za-z])", re.I)

# URLs worth checking for liveness: releases, weights, archives, data hosts.
ASSET_URL = re.compile(
    r"https?://[^\s\)\]\"'>]+?"
    r"(?:\.(?:pth|pt|ckpt|h5|npz|tar|tar\.gz|tgz|zip|bin|safetensors|onnx)"
    r"|drive\.google\.com/[^\s\)\]\"'>]+"
    r"|dropbox\.com/[^\s\)\]\"'>]+"
    r"|zenodo\.org/record[^\s\)\]\"'>]+"
    r"|figshare\.com/[^\s\)\]\"'>]+"
    r"|huggingface\.co/[^\s\)\]\"'>]+"
    r"|/releases/download/[^\s\)\]\"'>]+)",
    re.I)

# Language that gates access behind a human decision.
GATING = re.compile(
    r"(request access|upon request|apply for access|application form|"
    r"access (?:is )?granted|sign(?:ed)? (?:the )?(?:data )?(?:use |usage )?agreement|"
    r"data use agreement|\bDUA\b|\bEULA\b|registration (?:is )?required|"
    r"register (?:to|before) (?:download|access)|by application|"
    r"credentialed access|restricted access|fill (?:out|in) the form)", re.I)

FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
INDENT_BLOCK = re.compile(r"(?:^(?: {4}|\t)\S[^\n]*\n)+", re.M)


@dataclass
class CheckResult:
    criterion: str
    level: int
    evidence: str = ""
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["level_name"] = LEVEL_NAME[self.level]
        return d


# ------------------------------------------------------------------ helpers
def collect_docs(repo_dir: Path, max_files: int = 40, max_bytes: int = 400_000) -> list[tuple[Path, str]]:
    """Documentation files, README first. Bounded so one huge repo can't stall."""
    out: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        if p in seen or not p.is_file():
            return
        try:
            if p.stat().st_size > max_bytes:
                return
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        seen.add(p)
        out.append((p, txt))

    for p in sorted(repo_dir.glob("*")):
        if p.is_file() and p.stem.lower().startswith("readme"):
            add(p)
    for p in sorted(repo_dir.rglob("*")):
        if len(out) >= max_files:
            break
        if not p.is_file() or ".git" in p.parts:
            continue
        if p.suffix.lower() in (".md", ".rst", ".txt") and \
                any(n in p.stem.lower() for n in DOC_NAMES):
            add(p)
    return out


def code_blocks(text: str) -> list[str]:
    blocks = [m.group(1) for m in FENCE.finditer(text)]
    blocks += [m.group(0) for m in INDENT_BLOCK.finditer(text)]
    return blocks


ASSIGNED_VAR = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)=")


def find_placeholders(s: str) -> list[str]:
    """Placeholder tokens in a command, ignoring variables the snippet defines.

    `export NGPUS=8 && python ... --nproc_per_node=$NGPUS` is runnable exactly as
    written, so $NGPUS is not a placeholder. `$CONFIG` with no assignment is.
    """
    assigned = set(ASSIGNED_VAR.findall(s))
    hits = []
    for pat in PLACEHOLDER_PATTERNS:
        for m in re.finditer(pat, s):
            tok = m.group(0)
            if tok.startswith("$"):
                name = tok.lstrip("${").rstrip("}")
                if name in assigned:
                    continue
            hits.append(tok)
    return hits


# ------------------------------------------------------------------- checks
def check_concrete_run_command(docs) -> CheckResult:
    """7 of 16 artifact failures: a command exists but carries a placeholder.

    Grading is over the commands that plausibly *reproduce a number*, not over
    every command in the documentation. A repository whose evaluation command
    reads `--checkpoint /path/to/ckpt` is not reproducible just because its
    `pip install` line happens to be concrete — that was the first version of
    this check and it graded the wrong thing.
    """
    setup = re.compile(r"\b(pip|conda|apt-get|apt|venv|virtualenv|git\s+clone|"
                       r"poetry|npm|brew|wget|curl|unzip|tar)\b|requirements\.txt",
                       re.I)
    eval_concrete, eval_placeheld, other_concrete = [], [], []
    for path, text in docs:
        for block in code_blocks(text):
            for line in block.splitlines():
                if not RUN_TOKEN.match(line):
                    continue
                line = line.strip()
                if len(line) < 8 or line.startswith("#"):
                    continue
                ph = find_placeholders(line)
                is_eval = bool(EVAL_HINT.search(line)) and not setup.search(line)
                rec = (path.name, line, ph)
                if is_eval:
                    (eval_placeheld if ph else eval_concrete).append(rec)
                elif not ph and not setup.search(line):
                    other_concrete.append(rec)

    detail = {"n_eval_concrete": len(eval_concrete),
              "n_eval_placeholder": len(eval_placeheld),
              "n_other_concrete": len(other_concrete)}

    if eval_concrete:
        name, line, _ = eval_concrete[0]
        return CheckResult("concrete_run_command", FULL,
                           f"{name}: {line[:160]}", detail)
    if eval_placeheld:
        name, line, _ = eval_placeheld[0]
        detail["placeholders"] = sorted(
            {p for _n, _l, ps in eval_placeheld for p in ps})[:8]
        return CheckResult("concrete_run_command", PARTIAL,
                           f"evaluation command is placeholder-only — {name}: {line[:140]}",
                           detail)
    if other_concrete:
        name, line, _ = other_concrete[0]
        return CheckResult("concrete_run_command", PARTIAL,
                           f"commands documented but none reproduces a metric — "
                           f"{name}: {line[:120]}", detail)
    return CheckResult("concrete_run_command", ABSENT,
                       "no runnable command found in documentation", detail)


def check_documented_entrypoint(docs, repo_dir: Path) -> CheckResult:
    """4 of 16 failures: no documented route to a reported number at all."""
    for path, text in docs:
        for block in code_blocks(text):
            for line in block.splitlines():
                if RUN_TOKEN.match(line) and EVAL_HINT.search(line):
                    return CheckResult("documented_entrypoint", FULL,
                                       f"{path.name}: {line.strip()[:160]}", {"source": "docs"})
    scripts = [p for p in repo_dir.rglob("*")
               if p.is_file() and ".git" not in p.parts
               and p.suffix in (".py", ".sh") and EVAL_HINT.search(p.stem)]
    if scripts:
        rel = scripts[0].relative_to(repo_dir)
        return CheckResult("documented_entrypoint", PARTIAL,
                           f"script present but not documented: {rel}",
                           {"n_scripts": len(scripts), "source": "filesystem"})
    return CheckResult("documented_entrypoint", ABSENT, "no evaluation route documented or present", {})


def check_links_resolve(docs, online: bool, timeout: int = 12) -> CheckResult:
    """1 of 16 failures directly (a 404); time-dependent, so it grows with age."""
    urls: list[str] = []
    for _p, text in docs:
        urls += [m.group(0).rstrip(".,);") for m in ASSET_URL.finditer(text)]
    urls = list(dict.fromkeys(urls))
    if not urls:
        return CheckResult("links_resolve", FULL, "no declared asset URLs to verify",
                           {"n_urls": 0, "checked": False})
    if not online:
        return CheckResult("links_resolve", PARTIAL,
                           f"{len(urls)} asset URL(s) found; not checked (offline mode)",
                           {"n_urls": len(urls), "checked": False, "urls": urls[:10]})
    import urllib.error
    import urllib.request
    ok, bad = [], []
    for u in urls[:25]:
        req = urllib.request.Request(u, method="HEAD",
                                     headers={"User-Agent": "sraf-tierb/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                (ok if r.status < 400 else bad).append((u, r.status))
        except urllib.error.HTTPError as e:
            # Some hosts reject HEAD but serve GET; 403/405 is not link rot.
            (ok if e.code in (403, 405) else bad).append((u, e.code))
        except Exception as e:                                   # noqa: BLE001
            bad.append((u, type(e).__name__))
    if not bad:
        lvl, ev = FULL, f"all {len(ok)} declared asset URL(s) resolve"
    elif ok:
        lvl, ev = PARTIAL, f"{len(bad)} of {len(ok)+len(bad)} URL(s) failed: {bad[0][0][:90]}"
    else:
        lvl, ev = ABSENT, f"all {len(bad)} declared asset URL(s) failed: {bad[0][0][:90]}"
    return CheckResult("links_resolve", lvl, ev,
                       {"n_urls": len(urls), "checked": True,
                        "n_ok": len(ok), "n_bad": len(bad), "failures": bad[:5]})


def check_data_obtainable(docs) -> CheckResult:
    """1 of 16 failures: data released only on application."""
    for path, text in docs:
        m = GATING.search(text)
        if m:
            s = max(0, m.start() - 90)
            return CheckResult("data_obtainable_without_application", ABSENT,
                               f"{path.name}: ...{text[s:m.end()+90].strip()[:190]}...",
                               {"trigger": m.group(0)})
    return CheckResult("data_obtainable_without_application", FULL,
                       "no access-gating language found", {})


def check_repo_matches_paper(docs, paper_title: str | None) -> CheckResult:
    """3 of 16 failures: the linked repository is not the paper's code."""
    if not paper_title:
        return CheckResult("repo_matches_paper", PARTIAL,
                           "no paper title supplied — cannot compare", {"checked": False})
    stop = {"a", "an", "the", "of", "for", "and", "or", "with", "via", "on", "in",
            "to", "using", "by", "from", "is", "are", "at", "as", "towards", "toward"}

    def toks(s: str) -> set[str]:
        return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in stop and len(w) > 2}

    pt = toks(paper_title)
    if not pt:
        return CheckResult("repo_matches_paper", PARTIAL, "paper title has no usable tokens",
                           {"checked": False})
    best, where = 0.0, ""
    for path, text in docs:
        head = "\n".join(text.splitlines()[:60])
        rt = toks(head)
        if not rt:
            continue
        jacc = len(pt & rt) / len(pt)
        seq = SequenceMatcher(None, paper_title.lower(), head.lower()[:400]).ratio()
        score = max(jacc, seq)
        if score > best:
            best, where = score, path.name
    if best >= 0.45:
        lvl, ev = FULL, f"{where}: title overlap {best:.2f}"
    elif best >= 0.20:
        lvl, ev = PARTIAL, f"{where}: weak title overlap {best:.2f} — verify manually"
    else:
        lvl, ev = ABSENT, f"no documentation resembles the paper title (best {best:.2f})"
    return CheckResult("repo_matches_paper", lvl, ev, {"checked": True, "score": round(best, 3)})


# --------------------------------------------------------------------- API
def run_tier_b(repo_dir: str | Path, paper_title: str | None = None,
               online: bool = False) -> dict:
    repo_dir = Path(repo_dir)
    docs = collect_docs(repo_dir)
    results = [
        check_concrete_run_command(docs),
        check_documented_entrypoint(docs, repo_dir),
        check_links_resolve(docs, online=online),
        check_data_obtainable(docs),
        check_repo_matches_paper(docs, paper_title),
    ]
    return {
        "repo_dir": str(repo_dir),
        "n_doc_files": len(docs),
        "online": online,
        "checks": {r.criterion: r.as_dict() for r in results},
        "tier_b_level_sum": sum(r.level for r in results),
        "tier_b_max": 2 * len(results),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo_dir")
    ap.add_argument("--paper-title", default=None)
    ap.add_argument("--online", action="store_true",
                    help="verify declared asset URLs over the network")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    out = run_tier_b(a.repo_dir, a.paper_title, a.online)
    for name, c in out["checks"].items():
        print(f"  [{c['level_name']:7s}] {name:38s} {c['evidence'][:100]}")
    print(f"  -> {out['tier_b_level_sum']}/{out['tier_b_max']} "
          f"({out['n_doc_files']} doc files read)")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
