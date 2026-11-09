#!/usr/bin/env python3
"""Check everything that can fail before the N3 sweep spends money.

A corpus pass is roughly fifteen calls per study across ninety six studies, so
a wrong model id, a missing key or an unreachable endpoint is discovered
hundreds of calls in, after the budget has started draining. This runs first
and answers four questions:

  1. Is a credential present for every selected model?
  2. Does the provider accept the model id, right now?
  3. Do the recorded prices load into the meter, so the cap is armed?
  4. What is the estimated spend, against the remaining budget?

The reachability probe is a real completion capped at a handful of tokens. It
costs a fraction of a cent per model and is the only way to distinguish "the id
is wrong" from "the key is wrong" from "the endpoint is down" before committing
to a pass.

    python -m rag_pipeline.n3_preflight                 # whole registry
    python -m rag_pipeline.n3_preflight --models grok,gpt5
    python -m rag_pipeline.n3_preflight --no-probe      # offline checks only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from rag_pipeline.model_registry import (  # noqa: E402
    REGISTRY, N3_BUDGET_USD, ModelSpec, resolve, seed_prices,
)
from rag_pipeline.usage_meter import meter  # noqa: E402

PROBE_SYSTEM = "Reply with valid JSON only."
PROBE_USER = 'Return exactly this JSON and nothing else: {"ok": true}'


def check_key(spec: ModelSpec) -> tuple[bool, str]:
    if spec.api_key:
        return True, f"{spec.key_env} present"
    return False, f"{spec.key_env} NOT SET"


def probe(spec: ModelSpec) -> tuple[bool, str]:
    """One tiny completion. Confirms key, id and endpoint together."""
    from rag_pipeline.extractor import get_extractor
    try:
        ex = get_extractor(spec.backend, spec.model,
                           base_url=spec.base_url, api_key=spec.api_key or None)
    except Exception as e:  # noqa: BLE001
        return False, f"could not build extractor: {e}"
    try:
        raw = ex._complete(PROBE_SYSTEM, PROBE_USER)  # noqa: SLF001
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        hint = ""
        low = msg.lower()
        if "not found" in low or "does not exist" in low or "404" in msg:
            hint = "  <- model id is probably wrong"
        elif "auth" in low or "401" in msg or "403" in msg:
            hint = "  <- credential rejected"
        return False, f"{type(e).__name__}: {msg[:160]}{hint}"
    return True, f"responded ({len(raw or '')} chars)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=None,
                    help="comma-separated registry keys; default is all")
    ap.add_argument("--no-probe", action="store_true",
                    help="skip the live completion, check keys and prices only")
    args = ap.parse_args()

    specs = resolve(args.models)

    print("=" * 78)
    print("N3 preflight")
    print("=" * 78)
    print(f"{'key':14s} {'backend':10s} {'model':28s} {'scope':7s} {'est $':>7s}")
    print("-" * 78)
    for sp in specs:
        print(f"{sp.key:14s} {sp.backend:10s} {sp.model[:28]:28s} "
              f"{sp.scope:7s} {sp.estimated_usd():7.2f}")
    print("-" * 78)

    # ---- prices into the meter, so the cap is armed before any call
    seeded = seed_prices(meter, specs)
    meter.configure(budget_usd=N3_BUDGET_USD)
    already = meter.spend_usd()
    estimate = sum(sp.estimated_usd() for sp in specs)
    print(f"prices seeded for {len(seeded)} model(s)")
    print(f"estimated for this selection : ${estimate:7.2f}")
    print(f"already spent (meter state)  : ${already:7.2f}")
    print(f"budget                       : ${N3_BUDGET_USD:7.2f}")
    print(f"headroom after this selection: ${N3_BUDGET_USD - already - estimate:7.2f}")

    unpriced = meter.unpriced_models()
    if unpriced:
        print(f"\nWARNING: unpriced models already in the meter: {unpriced}")
        print("Their tokens are counted but not charged, so the cap does not "
              "protect against them.")

    # ---- credentials
    print("\ncredentials")
    print("-" * 78)
    failures = []
    for sp in specs:
        ok, msg = check_key(sp)
        print(f"  {'OK ' if ok else 'FAIL'}  {sp.key:14s} {msg}")
        if not ok:
            failures.append(sp.key)

    # ---- live probe
    if not args.no_probe:
        print("\nlive probe (one short completion each)")
        print("-" * 78)
        for sp in specs:
            if not sp.api_key:
                print(f"  SKIP  {sp.key:14s} no credential")
                continue
            ok, msg = probe(sp)
            print(f"  {'OK ' if ok else 'FAIL'}  {sp.key:14s} {msg}")
            if not ok and sp.key not in failures:
                failures.append(sp.key)
    else:
        print("\nlive probe skipped (--no-probe): model ids are UNVERIFIED")

    print("\n" + "=" * 78)
    if failures:
        print(f"NOT READY — {len(failures)} model(s) failed: {', '.join(failures)}")
        print("Fix these before starting a pass. A failure here costs nothing; "
              "the same failure mid-sweep costs the calls already made.")
        return 1
    if already + estimate > N3_BUDGET_USD:
        print("NOT READY — the estimate exceeds the remaining budget.")
        print("Narrow the selection, or raise SRAF_N3_BUDGET_USD deliberately.")
        return 1
    print("READY — all selected models reachable and the estimate fits the budget.")
    print("Next: python -m rag_pipeline.run_n3_frontier --models "
          + ",".join(sp.key for sp in specs) + " --limit 3   (smoke test first)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
