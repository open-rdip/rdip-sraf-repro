#!/usr/bin/env python3
"""Run the N3 frontier-model sweep, then the robustness re-run.

What this adds over `run_corpus_extraction`
-------------------------------------------
The corpus runner takes `SRAF_MODELS="backend:model,..."` and loops. That is
enough for models that share one endpoint and one scope. The N3 experiment does
not: each provider needs its own base URL and credential, the ceiling probe
covers the gold tier only, and the whole thing runs under a single spend cap
that must be armed with prices before the first call.

This driver resolves each model from the registry, hands the extractor its own
endpoint and key, narrows the study list when the scope says so, and stops the
entire sweep the moment the cap is crossed rather than carrying on into the
next model.

Order of operations, which is deliberate:

  1. seed prices, arm the cap          (an unpriced model disables the guard)
  2. per model, per study, extract     (resumable, marker file per pair)
  3. score every model against gold    (evaluation.compare_models)
  4. name the best uncontaminated one  (excludes Gemini, excludes the probe)
  5. hand it to the validity re-run    (analysis.criterion_validity)

Steps 3 to 5 are the robustness re-run: the point of N3 is not the extraction
table, it is whether the Phase 4 result survives a better extractor.

    python -m rag_pipeline.run_n3_frontier --models grok --limit 3   # smoke
    python -m rag_pipeline.run_n3_frontier                           # full plan
    python -m rag_pipeline.run_n3_frontier --rerun-only              # steps 3-5
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from rag_pipeline.model_registry import (  # noqa: E402
    GOLD_STUDIES, N3_BUDGET_USD, UNCONTAMINATED_CORPUS, ModelSpec,
    gold_repo_list, resolve, seed_prices,
)
from rag_pipeline.pipeline import model_slug, run  # noqa: E402
from rag_pipeline.extractor import set_study  # noqa: E402
from rag_pipeline.usage_meter import meter, BudgetExceeded  # noqa: E402

MARK_DIR = REPO_ROOT / "validation" / "extraction_done"
REPORT_DIR = REPO_ROOT / "analysis"
RUN_LOG = REPO_ROOT / "data" / "usage" / "n3_run_log.jsonl"


def _log(event: str, **fields) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **fields}
    with open(RUN_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def _rows_for(spec: ModelSpec) -> list[dict]:
    path = (gold_repo_list() if spec.scope == "gold"
            else Path(os.getenv("SRAF_REPO_LIST",
                                REPO_ROOT / "validation" / "repo_list.csv")))
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ── step 2: extraction ────────────────────────────────────────────────────────

def extract_for(spec: ModelSpec, limit: int = 0, force: bool = False) -> dict:
    slug = model_slug(spec.model)
    rows = _rows_for(spec)
    MARK_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {spec.key}  ({spec.backend}:{spec.model})  scope={spec.scope} "
          f"({len(rows)} studies, slug={slug}) ===")
    if spec.contaminated:
        print("    NOTE: contaminated model. Its score partly measures agreement "
              "with the family that produced the ground truth, and it is excluded "
              "from the headline comparison.")

    done = failed = skipped = 0
    for r in rows:
        sid = (r.get("study_id") or "").strip()
        pdf = (r.get("paper_url_pdf") or r.get("paper_url") or "").strip()
        if not sid:
            continue
        mark = MARK_DIR / f"{sid}__{slug}.done"
        if mark.exists() and not force:
            skipped += 1
            continue
        if not pdf.startswith("http"):
            print(f"    {sid}: no usable PDF url — skip")
            skipped += 1
            continue
        if limit and done + failed >= limit:
            print(f"    reached --limit {limit}")
            break

        set_study(sid)
        try:
            res = run(study_id=sid, pdf_url=pdf, backend=spec.backend,
                      model=spec.model)
            mark.write_text(json.dumps(res))
            done += 1
            print(f"    {sid}: +{res.get('triples_added', 0)} triples "
                  f"(seeds={res.get('seeds_found', 0)}, "
                  f"params={res.get('params_found', 0)}, "
                  f"evals={res.get('evals_found', 0)})   "
                  f"spend ${meter.spend_usd():.2f}")
        except BudgetExceeded as e:
            print(f"\n    {sid}: ABORTING SWEEP — {e}")
            _log("budget_exceeded", model=spec.key, study=sid,
                 spend=meter.spend_usd())
            raise
        except Exception as e:  # noqa: BLE001 — one bad paper must not stop a pass
            failed += 1
            print(f"    {sid}: extraction FAILED — {type(e).__name__}: {str(e)[:140]}")
            _log("study_failed", model=spec.key, study=sid, error=str(e)[:300])
        finally:
            set_study(None)

    summary = {"model": spec.key, "slug": slug, "done": done,
               "failed": failed, "skipped": skipped,
               "spend_usd": round(meter.spend_usd(spec.model), 4)}
    _log("model_complete", **summary)
    print(f"    -> {done} extracted, {failed} failed, {skipped} skipped, "
          f"${summary['spend_usd']:.2f} on this model")
    return summary


# ── steps 3 to 5: the robustness re-run ───────────────────────────────────────

def _py(*args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, *args]
    print(f"\n$ {' '.join(cmd)}")
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True,
                          capture_output=True)


def score_all(tier: str = "gold", match: str = "fuzzy") -> dict | None:
    """Score every discovered model against the ground truth."""
    out = REPORT_DIR / f"n3_compare_{tier}_{match}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    p = _py("-m", "evaluation.compare_models", "--tier", tier,
            "--match", match, "--json", str(out))
    print(p.stdout[-4000:] or p.stderr[-2000:])
    if p.returncode != 0:
        print(f"compare_models failed ({p.returncode}); see output above")
        return None
    try:
        return json.loads(out.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def pick_best(compare: dict, specs: list[ModelSpec]) -> str | None:
    """Best uncontaminated full-corpus model by headline F1.

    Gemini is excluded because the ground truth came from its family. The
    ceiling probe is excluded because it covers only the gold tier, so its
    score is not comparable with a corpus pass.
    """
    eligible = {model_slug(sp.model): sp.key
                for sp in specs
                if sp.key in UNCONTAMINATED_CORPUS}
    best, best_f1 = None, -1.0
    for slug, payload in (compare.get("models") or compare).items():
        if slug not in eligible:
            continue
        f1 = None
        if isinstance(payload, dict):
            f1 = (payload.get("headline", {}) or {}).get("f1")
            if f1 is None:
                f1 = payload.get("f1")
        if f1 is not None and float(f1) > best_f1:
            best, best_f1 = slug, float(f1)
    if best:
        print(f"\nbest uncontaminated corpus model: {best} "
              f"({eligible[best]}) headline F1 {best_f1:.3f}")
    else:
        print("\ncould not identify a best model from the comparison output; "
              "pass --best-slug explicitly to run the validity step")
    return best


def rerun_validity(best_slug: str) -> bool:
    """Re-run the criterion-level validity analysis on the re-scored corpus."""
    p = _py("-m", "analysis.criterion_validity")
    print(p.stdout[-6000:] or p.stderr[-2000:])
    if p.returncode != 0:
        print(f"criterion_validity failed ({p.returncode})")
        return False
    _log("validity_rerun", best_slug=best_slug)
    print("\nThe question this answers: does the Phase 4 null survive a better "
          "extractor? Compare the output above with analysis/criterion_validity.md "
          "as committed, and report BOTH, whichever way it goes.")
    return True


# ── driver ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=None,
                    help="comma-separated registry keys; default is the whole plan")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop each model after N studies (smoke test)")
    ap.add_argument("--force", action="store_true",
                    help="re-extract studies already marked done")
    ap.add_argument("--tier", default="gold", choices=["gold", "silver"])
    ap.add_argument("--match", default="fuzzy", choices=["exact", "fuzzy"])
    ap.add_argument("--rerun-only", action="store_true",
                    help="skip extraction, run scoring and the validity re-run")
    ap.add_argument("--best-slug", default=None,
                    help="skip model selection and use this slug for the re-run")
    ap.add_argument("--no-rerun", action="store_true",
                    help="extract only, do not score or re-run validity")
    args = ap.parse_args()

    specs = resolve(args.models)

    seed_prices(meter, specs)
    meter.configure(budget_usd=N3_BUDGET_USD)
    print(f"budget ${N3_BUDGET_USD:.2f}, already spent ${meter.spend_usd():.2f}")

    if not args.rerun_only:
        missing = [s.key for s in specs if not s.api_key]
        if missing:
            print(f"ABORT: no credential for {missing}. "
                  f"Run python -m rag_pipeline.n3_preflight first.")
            return 1
        _log("sweep_start", models=[s.key for s in specs], limit=args.limit,
             budget=N3_BUDGET_USD)
        try:
            for spec in specs:
                extract_for(spec, limit=args.limit, force=args.force)
        except BudgetExceeded:
            print("\n" + meter.summary())
            return 2
        print("\n" + meter.summary())

    if args.no_rerun:
        return 0

    compare = score_all(tier=args.tier, match=args.match)
    best = args.best_slug or (pick_best(compare, specs) if compare else None)
    if not best:
        print("\nStopping before the validity re-run: no best model identified.")
        return 1
    return 0 if rerun_validity(best) else 1


if __name__ == "__main__":
    raise SystemExit(main())
