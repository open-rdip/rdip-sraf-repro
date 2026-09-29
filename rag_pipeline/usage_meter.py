"""Token and spend accounting for paid-API extraction runs (contribution N3).

Two jobs:

1. **Stop a runaway run.** A corpus pass is 95 studies times several chunks times
   several models. Against a paid endpoint, an unattended run with a bad prompt
   or a retry loop can spend the whole budget before anyone notices. Every
   completion is metered and the run aborts the moment the cap is crossed.

2. **Produce the cost data N7 needs.** The selective-verification cost model
   needs per-study extraction cost. Recording it during the run is the only
   chance to get it; it cannot be reconstructed afterwards.

State is written to disk after every call, so a resumed run continues counting
from where the previous one stopped rather than starting the budget over.

    from rag_pipeline.usage_meter import meter

    meter.configure(budget_usd=35.0)
    ...
    meter.record("gpt-5", prompt_tokens=1800, completion_tokens=240, study="study009")
    print(meter.summary())

Prices are NOT baked in as fact. They change, and a wrong price makes the guard
useless in the dangerous direction. Set them from the provider's own pricing
page before a paid run:

    meter.set_price("gpt-5", prompt_per_mtok=..., completion_per_mtok=...)

or via data/usage/prices.json. Any model with no price recorded still has its
tokens counted, and `summary()` flags it, so an unpriced model cannot silently
pass the budget check.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
USAGE_DIR = Path(os.getenv("SRAF_USAGE_DIR", REPO_ROOT / "data" / "usage"))
STATE_PATH = USAGE_DIR / "usage.json"
PRICES_PATH = USAGE_DIR / "prices.json"


class BudgetExceeded(RuntimeError):
    """Raised when a recorded call takes the run past its spend cap."""


@dataclass
class Price:
    prompt_per_mtok: float
    completion_per_mtok: float


@dataclass
class ModelUsage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    per_study: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class UsageMeter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usage: dict[str, ModelUsage] = {}
        self._prices: dict[str, Price] = {}
        self._budget_usd: float | None = None
        self._loaded = False

    # ── configuration ────────────────────────────────────────────────────────

    def configure(self, budget_usd: float | None = None, reset: bool = False) -> None:
        """Set the spend cap. `reset=True` starts the tally from zero, which is
        what you want for a genuinely new experiment and never want on a resume."""
        self._load()
        if reset:
            self._usage = {}
            self._persist()
        if budget_usd is not None:
            self._budget_usd = float(budget_usd)

    def set_price(self, model: str, prompt_per_mtok: float,
                  completion_per_mtok: float, persist: bool = True) -> None:
        self._load()
        self._prices[model] = Price(prompt_per_mtok, completion_per_mtok)
        if persist:
            USAGE_DIR.mkdir(parents=True, exist_ok=True)
            PRICES_PATH.write_text(json.dumps(
                {m: asdict(p) for m, p in self._prices.items()}, indent=2))

    # ── recording ────────────────────────────────────────────────────────────

    def record(self, model: str, prompt_tokens: int, completion_tokens: int,
               study: str | None = None) -> None:
        """Record one completion. Raises BudgetExceeded if this call crosses the
        cap — after the tokens are persisted, so the record stays accurate."""
        self._load()
        with self._lock:
            u = self._usage.setdefault(model, ModelUsage())
            u.calls += 1
            u.prompt_tokens += int(prompt_tokens or 0)
            u.completion_tokens += int(completion_tokens or 0)
            if study:
                s = u.per_study.setdefault(study, {"calls": 0, "prompt": 0, "completion": 0})
                s["calls"] += 1
                s["prompt"] += int(prompt_tokens or 0)
                s["completion"] += int(completion_tokens or 0)
            self._persist()

        if self._budget_usd is not None:
            spent = self.spend_usd()
            if spent > self._budget_usd:
                raise BudgetExceeded(
                    f"spend cap reached: ${spent:.2f} of ${self._budget_usd:.2f} "
                    f"after {self.total_calls()} calls. Tokens are recorded in "
                    f"{STATE_PATH}; raise the cap or narrow the run to continue."
                )

    # ── reporting ────────────────────────────────────────────────────────────

    def spend_usd(self, model: str | None = None) -> float:
        self._load()
        models = [model] if model else list(self._usage)
        total = 0.0
        for m in models:
            u = self._usage.get(m)
            p = self._price_for(m)
            if not u or not p:
                continue
            total += (u.prompt_tokens / 1e6) * p.prompt_per_mtok
            total += (u.completion_tokens / 1e6) * p.completion_per_mtok
        return total

    def unpriced_models(self) -> list[str]:
        self._load()
        return sorted(m for m in self._usage if not self._price_for(m))

    def total_calls(self) -> int:
        self._load()
        return sum(u.calls for u in self._usage.values())

    def summary(self) -> str:
        self._load()
        if not self._usage:
            return "no usage recorded"
        rows = ["model                                    calls    prompt  completion     cost",
                "-" * 84]
        for m in sorted(self._usage):
            u = self._usage[m]
            p = self._price_for(m)
            cost = f"${self.spend_usd(m):7.2f}" if p else "  unpriced"
            rows.append(f"{m[:38]:38s} {u.calls:7d} {u.prompt_tokens:9d} "
                        f"{u.completion_tokens:11d} {cost}")
        rows.append("-" * 84)
        rows.append(f"{'total':38s} {self.total_calls():7d} "
                    f"{sum(u.prompt_tokens for u in self._usage.values()):9d} "
                    f"{sum(u.completion_tokens for u in self._usage.values()):11d} "
                    f"${self.spend_usd():7.2f}")
        if self._budget_usd is not None:
            rows.append(f"budget ${self._budget_usd:.2f}, "
                        f"remaining ${max(0.0, self._budget_usd - self.spend_usd()):.2f}")
        missing = self.unpriced_models()
        if missing:
            rows.append("")
            rows.append("WARNING: no price set for " + ", ".join(missing) +
                        " — their tokens are counted but not charged against the "
                        "budget, so the cap is not protecting you for them.")
        return "\n".join(rows)

    def per_study_costs(self, model: str) -> dict[str, float]:
        """Cost per study for one model. This is the input N7 needs."""
        self._load()
        u = self._usage.get(model)
        p = self._price_for(model)
        if not u or not p:
            return {}
        return {
            sid: (v["prompt"] / 1e6) * p.prompt_per_mtok
                 + (v["completion"] / 1e6) * p.completion_per_mtok
            for sid, v in u.per_study.items()
        }

    # ── internals ────────────────────────────────────────────────────────────

    def _price_for(self, model: str) -> Price | None:
        if model in self._prices:
            return self._prices[model]
        # Allow a prefix entry ("gpt-5") to price a dated id ("gpt-5-2026-01-01").
        for key, price in self._prices.items():
            if model.startswith(key):
                return price
        return None

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if STATE_PATH.exists():
            try:
                raw = json.loads(STATE_PATH.read_text())
                for m, d in raw.get("models", {}).items():
                    self._usage[m] = ModelUsage(
                        calls=d.get("calls", 0),
                        prompt_tokens=d.get("prompt_tokens", 0),
                        completion_tokens=d.get("completion_tokens", 0),
                        per_study=d.get("per_study", {}),
                    )
            except (json.JSONDecodeError, OSError):
                pass
        if PRICES_PATH.exists():
            try:
                for m, d in json.loads(PRICES_PATH.read_text()).items():
                    self._prices[m] = Price(**d)
            except (json.JSONDecodeError, OSError, TypeError):
                pass

    def _persist(self) -> None:
        USAGE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(
            {"models": {m: asdict(u) for m, u in self._usage.items()}}, indent=2))
        tmp.replace(STATE_PATH)


meter = UsageMeter()


def record_openai_usage(resp, model: str, study: str | None = None) -> None:
    """Record from an OpenAI-style response object, tolerating a missing usage
    block rather than failing the extraction."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return
    meter.record(
        model,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        study=study,
    )
