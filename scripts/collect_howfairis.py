#!/usr/bin/env python3
"""Collect howfairis scores for the corpus (N2, second instrument).

Why howfairis and not F-UJI as the headline comparison
------------------------------------------------------
F-UJI assesses data objects: it resolves a PID, pulls metadata from DataCite,
re3data and landing pages, and scores metadata richness. A GitHub repository
exposes none of that, so F-UJI would score the whole corpus at the floor and
the resulting invariance would be an artifact of pointing a dataset tool at
software, not a property of the literature. That is the mirror image of the
N1 finding (ceiling saturation) and conflating the two would be the weakest
moment in the paper.

howfairis is scope-correct: it evaluates a source-code repository against the
five fair-software.eu recommendations, which is what this corpus actually is.
F-UJI still belongs in the paper, but scoped to the subset of studies that
carry a Zenodo DOI, where the instrument is in scope.

Each check is binary, so this instrument has no point budget. The comparable
statistic across instruments is the proportion of criteria with zero observed
variance, not a percentage of points.

Run it with the isolated interpreter, because howfairis pins click<8 and will
downgrade a shared environment:

    python3 -m venv ~/.venvs/howfairis && ~/.venvs/howfairis/bin/pip install howfairis
    export APIKEY_GITHUB=ghp_...          # 96 repos needs an authenticated token
    ~/.venvs/howfairis/bin/python scripts/collect_howfairis.py

Resumable: one cache file per study, already-done studies are skipped.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "howfairis"
REPO_LIST = Path(os.getenv("SRAF_REPO_LIST", REPO_ROOT / "validation" / "repo_list.csv"))

# The five fair-software.eu recommendations, in howfairis' own order.
CHECKS = ["repository", "license", "registry", "citation", "checklist"]


def _require_howfairis():
    try:
        from howfairis import Checker, Repo  # noqa: F401
    except ImportError:
        sys.exit(
            "howfairis is not importable by this interpreter.\n"
            "It pins click<8 and will break camelot-py and magika if installed\n"
            "into a shared environment, so use a dedicated one:\n"
            "  python3 -m venv ~/.venvs/howfairis\n"
            "  ~/.venvs/howfairis/bin/pip install howfairis\n"
            "  ~/.venvs/howfairis/bin/python scripts/collect_howfairis.py"
        )
    from howfairis import Checker, Repo
    return Checker, Repo


def rate_limit_note() -> str:
    if os.getenv("APIKEY_GITHUB"):
        return "APIKEY_GITHUB is set (5000 req/hour)."
    return ("APIKEY_GITHUB is NOT set. Unauthenticated GitHub allows 60 requests "
            "per hour and howfairis spends several per repository, so a full "
            "corpus pass will rate-limit. Set a token before the real run.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="stop after N studies")
    ap.add_argument("--force", action="store_true", help="re-check cached studies")
    ap.add_argument("--sleep", type=float, default=1.0,
                    help="seconds between repositories (default 1.0)")
    args = ap.parse_args()

    Checker, Repo = _require_howfairis()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(rate_limit_note())

    with open(REPO_LIST, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    print(f"{len(rows)} studies in {REPO_LIST.name}; cache at {OUT_DIR}")

    done = failed = skipped = 0
    for r in rows:
        sid = (r.get("study_id") or "").strip()
        url = (r.get("repo_url") or "").strip()
        if not sid or not url:
            continue
        out = OUT_DIR / f"{sid}.json"
        if out.exists() and not args.force:
            skipped += 1
            continue
        if args.limit and done + failed >= args.limit:
            print(f"reached --limit {args.limit}")
            break

        rec = {"study_id": sid, "repo_url": url,
               "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        try:
            comp = Checker(Repo(url), is_quiet=True).check_five_recommendations()
            for k in CHECKS:
                rec[k] = bool(getattr(comp, k))
            rec["n_passed"] = sum(rec[k] for k in CHECKS)
            rec["error"] = None
            done += 1
            marks = "".join("Y" if rec[k] else "." for k in CHECKS)
            print(f"  {sid}: {marks}  ({rec['n_passed']}/5)  {url}")
        except Exception as e:  # noqa: BLE001 — one bad repo must not stop the pass
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
            for k in CHECKS:
                rec[k] = None
            rec["n_passed"] = None
            failed += 1
            print(f"  {sid}: FAILED — {rec['error']}")
        out.write_text(json.dumps(rec, indent=2))
        time.sleep(args.sleep)

    print(f"\n{done} checked, {failed} failed, {skipped} already cached.")
    if failed:
        print("Failed studies keep an error record; re-run with --force to retry them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
