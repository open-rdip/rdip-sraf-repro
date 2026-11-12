#!/usr/bin/env python3
"""Harvest ReScience C replications as N10 badged-contrast candidates.

Why this source
---------------
The ACM Digital Library went fully open access in January 2026, but its search
sits behind bot verification that this pipeline does not attempt to bypass, so
the badge facet has to be driven by hand in a browser. ReScience C has no such
barrier and publishes structured metadata per article, which makes the
machine-readable half of the W.6 protocol automatable.

What it gives and what it does not
----------------------------------
`article.yaml` carries the replication's own title (prefixed `[Re]` when the
replication succeeded and `[not-Re]` when it did not), the ORIGINAL paper's
citation, DOI and PDF URL, the domain, and the language.

It does NOT say whether the replicators ran the authors' code or re-implemented
from scratch. That distinction is the whole inclusion criterion for this
stratum (paper_notes W.2): a from-scratch replication certifies the method, not
the artifact, and SRAF audits the artifact. It can only be decided by reading
the report, so this script marks every row `authors_code: UNVERIFIED` and the
check stays manual.

The `code` field in the yaml is the REPLICATION's repository, never the
original's. Writing it into repo_url would audit twenty replication
repositories and answer nothing (W.6).

    python scripts/harvest_rescience.py --out validation/rescience_candidates.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request

#: Two sources with the same metadata schema under different filenames.
#: ReScience/articles is the general journal (mostly computational
#: neuroscience). ReScience/MLRC is the ML Reproducibility Challenge, which is
#: where the NeurIPS / ICML / ICLR / CVPR replications are, and therefore where
#: anything matching the 96-study corpus will come from.
SOURCES = [
    {"repo": "ReScience/articles", "label": "rescience-c", "file": "article.yaml"},
    {"repo": "ReScience/MLRC", "label": "mlrc", "file": "metadata.yaml"},
]

#: Domains that plausibly match the 96-study corpus, which is ML research
#: (mostly vision and NLP) from Papers with Code. Deliberately broad here;
#: narrowing happens at the manual stage with a human reading the title.
ML_DOMAIN = re.compile(
    r"machine\s*learning|deep\s*learning|artificial\s*intelligence|computer\s*vision|"
    r"natural\s*language|neural|reinforcement|data\s*science|information\s*retrieval|"
    r"recommend|ml\s+reproducibility", re.I)


def get(url: str, tries: int = 3) -> bytes | None:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rdip-sraf/1.0"})
            with urllib.request.urlopen(req, timeout=30) as fh:
                return fh.read()
        except Exception as exc:
            if i == tries - 1:
                print(f"    fetch failed: {url} ({exc})", file=sys.stderr)
            time.sleep(1.5 * (i + 1))
    return None


def scalar(block: str, key: str) -> str:
    """Pull a single scalar out of a yaml block without a yaml dependency.

    The files are hand-written from a template and full of comments, so this is
    deliberately forgiving: it takes the first non-empty value for the key and
    strips any trailing '# comment'.
    """
    m = re.search(rf"^\s*-?\s*{key}\s*:\s*(.+)$", block, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    v = re.sub(r"\s+#.*$", "", v).strip().strip('"').strip("'")
    return v


def parse(doi_dir: str, text: str, source: str = "") -> dict:
    title = scalar(text, "title")
    # the replication section holds the ORIGINAL paper's details
    rep = text.split("replication:", 1)[1] if "replication:" in text else ""
    rep = rep.split("\nabstract:", 1)[0]
    succeeded = title.startswith("[Re]")
    failed = title.startswith("[¬Re]") or title.startswith("[not-Re]")
    return {
        "source": source,
        "rescience_dir": doi_dir,
        "replication_title": title,
        "outcome": "reproduced" if succeeded else ("not_reproduced" if failed else "other"),
        "domain": scalar(text, "domain"),
        "language": scalar(text, "language"),
        "original_cite": scalar(rep, "cite"),
        "original_doi": scalar(rep, "doi"),
        "original_url": scalar(rep, "url"),
        "replication_code": scalar(text.split("replication:", 1)[0], "url"),
        "review_url": scalar(text.split("review:", 1)[-1], "url") if "review:" in text else "",
        "authors_code": "UNVERIFIED",   # W.2: must be read from the report
        "repo_url": "",                 # the ORIGINAL paper's repo, filled by hand
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="validation/rescience_candidates.csv")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = []
    for src in SOURCES:
        # One recursive tree call lists every path in the repo. The previous
        # version made an API call per directory and then guessed the layout,
        # which cost a wasted 404 and a retry sleep on most of them. MLRC alone
        # has three different layouts across its three years; asking the tree
        # removes the guessing entirely.
        tree = None
        for branch in ("master", "main"):
            raw = get(f"https://api.github.com/repos/{src['repo']}/git/trees/"
                      f"{branch}?recursive=1")
            if raw:
                tree = json.loads(raw)
                if tree.get("tree"):
                    break
        if not tree or not tree.get("tree"):
            print(f"  {src['label']}: could not read tree", file=sys.stderr)
            continue
        paths = sorted(e["path"] for e in tree["tree"]
                       if e.get("type") == "blob"
                       and e["path"].endswith("/" + src["file"]))
        if tree.get("truncated"):
            print(f"  {src['label']}: WARNING tree truncated by the API",
                  file=sys.stderr)
        if args.limit:
            paths = paths[:args.limit]
        print(f"  {src['label']}: {len(paths)} {src['file']} files", flush=True)

        for i, path in enumerate(paths, 1):
            blob = get(f"https://raw.githubusercontent.com/{src['repo']}/"
                       f"{branch}/{path}", tries=2)
            if not blob:
                continue
            try:
                rows.append(parse(os.path.dirname(path),
                                  blob.decode("utf-8", "replace"), src["label"]))
            except Exception as exc:
                print(f"    parse failed for {path}: {exc}", file=sys.stderr)
            if i % 40 == 0:
                print(f"    {i}/{len(paths)}", flush=True)

    ml = [r for r in rows
          if ML_DOMAIN.search(r["domain"] or "")
          and r["outcome"] == "reproduced"
          and (r["language"] or "").lower().startswith("python")]

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(ml)

    print(f"\n  harvested {len(rows)} articles")
    print(f"  reproduced + python + ML-ish domain: {len(ml)}  -> {args.out}")
    from collections import Counter
    print("\n  outcomes:", dict(Counter(r["outcome"] for r in rows)))
    print("  top domains:")
    for dom, n in Counter(r["domain"] for r in rows).most_common(12):
        print(f"    {n:>3}  {dom}")
    print("\n  NOTE: authors_code is UNVERIFIED on every row. W.2 requires the")
    print("  report to state the replicators ran the ORIGINAL authors' code.")
    print("  repo_url is empty: it must be the ORIGINAL paper's repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
