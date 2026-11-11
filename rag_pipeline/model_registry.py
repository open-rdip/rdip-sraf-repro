"""The frontier-model set for contribution N3, declared in one place.

Why a registry rather than environment variables
------------------------------------------------
The N3 experiment asks whether an entity-level F1 of about 0.27 is a property
of the artifacts or of a quantised 24B model. Answering it means running several
hosted models over the same corpus under the same prompt, then re-scoring and
re-running the validity analysis with the best one.

That experiment has to be reconstructible by someone else, which the previous
arrangement did not support: each provider needed its own base URL and key in
globals that can only describe one endpoint at a time, so "which models were
run, at what prices, over what scope" lived in a submission command rather than
in the repository. This module makes those facts data.

Each entry carries:

  backend / model   how to reach it
  key_env           the environment variable holding its credential
  base_url          explicit, so two providers can run in one process
  prompt/completion published price per million tokens, used by the spend cap
  scope             "corpus" (all studies) or "gold" (the 12 gold studies)
  contaminated      True if the ground truth was produced by this model family
  note              why the entry exists, in one line

A WARNING ABOUT MODEL IDS
-------------------------
Provider model identifiers change, and a wrong id fails late and expensively.
The ids below are the ones the cost plan was built on, each overridable by
environment variable, and `rag_pipeline.n3_preflight` verifies every one of
them against the live provider before any corpus pass starts. Do not trust this
file as a record of what exists today; trust the preflight.

    from rag_pipeline.model_registry import REGISTRY, resolve, seed_prices
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Total cap for the whole N3 experiment. The plan spends about $21.70 of this;
# the headroom absorbs retries and a re-run of one model, not a second sweep.
N3_BUDGET_USD = float(os.getenv("SRAF_N3_BUDGET_USD", "35"))

# Prices below are calibrated against observed provider billing, not copied
# from rate cards. After the 10 Nov 2026 sweep, OpenAI and Anthropic matched
# the computed cost to the cent while Google was out by 3.32x and xAI by 1.56x
# over identical token counts. Since the two that matched are exact, the token
# accounting is sound and the error was in the prices, so the prices were
# corrected from the bills. Re-check after any provider price change: an
# under-priced model makes the spend cap guard a smaller number than the one
# actually being spent, which is the quiet way a budget guard stops working.

# ── Planning assumptions ──────────────────────────────────────────────────────
# These three numbers reproduce the cost table the $35 budget was approved
# against, and they are recorded here so that the figure can be rederived
# rather than taken on trust.
#
# One call is made per deduplicated retrieved chunk. Six fixed queries times
# three chunks is eighteen, which deduplicates to about fifteen. A chunk is 400
# words, roughly 530 tokens, and the prompt template adds about 300, which is
# where 845 comes from. The completion is a single JSON object over seven
# fields.
#
# Sensitivity worth knowing before a run: the prompt figure is the one that
# moves. Raising chunk size or top_k raises it proportionally, and the plan has
# roughly $13 of headroom, so a doubling of prompt size would take the sweep
# over budget. The cap catches that, but the preflight estimate will not.
CALLS_PER_STUDY = int(os.getenv("SRAF_N3_CALLS_PER_STUDY", "15"))
PROMPT_TOKENS_PER_CALL = int(os.getenv("SRAF_N3_PROMPT_TOKENS", "845"))
COMPLETION_TOKENS_PER_CALL = int(os.getenv("SRAF_N3_COMPLETION_TOKENS", "297"))

# The twelve studies carrying a hand-verified gold annotation. The ceiling
# probe runs on these only, because that is the tier its result is read against.
GOLD_STUDIES = [
    "study001", "study002", "study003", "study005", "study006", "study008",
    "study009", "study013", "study015", "study017", "study020", "study022",
]


@dataclass(frozen=True)
class ModelSpec:
    key: str                      # short handle used on the command line
    backend: str                  # extractor backend
    model: str                    # provider model id
    key_env: str                  # env var holding the credential
    prompt_per_mtok: float
    completion_per_mtok: float
    scope: str = "corpus"         # "corpus" | "gold"
    contaminated: bool = False
    base_url: str | None = None
    note: str = ""
    extra_env: tuple[str, ...] = field(default_factory=tuple)

    @property
    def api_key(self) -> str:
        return os.getenv(self.key_env, "")

    @property
    def n_studies(self) -> int:
        return len(GOLD_STUDIES) if self.scope == "gold" else 96

    def estimated_usd(self, calls_per_study: int = CALLS_PER_STUDY,
                      prompt_tokens: int = PROMPT_TOKENS_PER_CALL,
                      completion_tokens: int = COMPLETION_TOKENS_PER_CALL) -> float:
        """Cost of one pass at this scope, on the committed planning assumptions.

        An estimate for planning, not an accounting figure. The meter records
        what is actually spent, and the cap acts on that rather than on this.
        """
        calls = calls_per_study * self.n_studies
        return (calls * prompt_tokens / 1e6) * self.prompt_per_mtok + \
               (calls * completion_tokens / 1e6) * self.completion_per_mtok


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


REGISTRY: dict[str, ModelSpec] = {
    spec.key: spec for spec in [
        ModelSpec(
            key="gemini-flash",
            backend="google",
            model=_env("SRAF_N3_GEMINI_MODEL", "gemini-3.8-flash"),
            key_env="GOOGLE_API_KEY",
            # Calibrated 10 Nov 2026 against the provider's own billing, which
            # read 91.07 THB (about $2.72 at 33.44 THB/USD) where the previous
            # 0.75/3.75 computed $0.82 over the same 0.48M tokens: a factor of
            # 3.32. Scaled both directions by that factor, preserving their
            # ratio. See the note in paper_notes AC.5 for the two candidate
            # causes and why this is a calibration rather than a rate card.
            prompt_per_mtok=2.49, completion_per_mtok=12.45,
            scope="corpus", contaminated=True,
            note=("Ground truth candidates were generated by this family, so its "
                  "score partly measures family agreement. Run it, report it "
                  "apart, label the confound."),
        ),
        ModelSpec(
            key="grok",
            backend="xai",
            model=_env("SRAF_N3_GROK_MODEL", "grok-4.7"),
            key_env="XAI_API_KEY",
            # Calibrated 10 Nov 2026: billed $4.59 where 2.00/6.00 computed
            # $2.94 over the same 1.10M tokens, a factor of 1.56.
            prompt_per_mtok=3.12, completion_per_mtok=9.36,
            note="Uncontaminated full-corpus pass.",
        ),
        ModelSpec(
            key="gpt5",
            backend="openai",
            model=_env("SRAF_N3_GPT_MODEL", "gpt-5"),
            key_env="OPENAI_API_KEY",
            prompt_per_mtok=1.25, completion_per_mtok=10.00,
            note="Uncontaminated full-corpus pass.",
        ),
        ModelSpec(
            key="sonnet",
            backend="anthropic",
            model=_env("SRAF_N3_SONNET_MODEL", "claude-sonnet-5-5"),
            key_env="ANTHROPIC_API_KEY",
            prompt_per_mtok=2.00, completion_per_mtok=10.00,
            note="Uncontaminated full-corpus pass.",
        ),
        ModelSpec(
            key="opus",
            backend="anthropic",
            model=_env("SRAF_N3_OPUS_MODEL", "claude-opus-5-5"),
            key_env="ANTHROPIC_API_KEY",
            prompt_per_mtok=4.00, completion_per_mtok=20.00,
            scope="gold",
            note=("Ceiling probe on the 12 gold studies only. Establishes how "
                  "much headroom remains above the best full-corpus model "
                  "without paying for a fifth corpus pass."),
        ),
        # --- Open-weight models, served locally by vLLM on the ASL cluster.
        # No credential and no meter cost: the compute is the cluster's, not a
        # provider's. `key_env` names the one variable that must be set for
        # these to resolve, which is the server URL rather than a key.
        # Same three checkpoints as the ungrounded corpus pass, so the grounded
        # result is comparable to it line for line.
        ModelSpec(
            key="qwen",
            backend="vllm",
            model=_env("SRAF_OW_QWEN_MODEL", "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8"),
            key_env="VLLM_SERVER_URL",
            prompt_per_mtok=0.0, completion_per_mtok=0.0,
            scope="gold",
            note="Open-weight grounded pilot. Local compute, no provider cost.",
        ),
        ModelSpec(
            key="llama",
            backend="vllm",
            model=_env("SRAF_OW_LLAMA_MODEL",
                       "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"),
            key_env="VLLM_SERVER_URL",
            prompt_per_mtok=0.0, completion_per_mtok=0.0,
            scope="gold",
            note=("Open-weight grounded pilot. Reports seeds in 52 of 95 studies "
                  "where all four frontier corpus models independently find 2, so "
                  "the span check tests that anomaly directly."),
        ),
        ModelSpec(
            key="mistral",
            backend="vllm",
            model=_env("SRAF_OW_MISTRAL_MODEL",
                       "RedHatAI/Mistral-Small-24B-Instruct-2501-quantized.w8a8"),
            key_env="VLLM_SERVER_URL",
            prompt_per_mtok=0.0, completion_per_mtok=0.0,
            scope="gold",
            note="Open-weight grounded pilot. Leads the ungrounded F1 table.",
        ),
    ]
}

#: The three models whose scores carry the headline claim. Gemini is excluded
#: because of the contamination, and Opus because it does not cover the corpus.
UNCONTAMINATED_CORPUS = ("grok", "gpt5", "sonnet")

#: Locally served open-weight checkpoints. Separated from the hosted models
#: because they carry no provider cost and no contamination question.
OPEN_WEIGHTS = ("qwen", "llama", "mistral")


def resolve(keys: str | list[str] | None = None) -> list[ModelSpec]:
    """Resolve a comma-separated selection, or the whole registry in plan order."""
    if keys is None:
        return list(REGISTRY.values())
    if isinstance(keys, str):
        keys = [k.strip() for k in keys.split(",") if k.strip()]
    missing = [k for k in keys if k not in REGISTRY]
    if missing:
        raise KeyError(
            f"unknown model key(s) {missing}; known keys: {sorted(REGISTRY)}")
    return [REGISTRY[k] for k in keys]


def seed_prices(meter, specs: list[ModelSpec] | None = None) -> list[str]:
    """Register every spec's price with the usage meter.

    This is not a convenience. The meter counts tokens for a model it has no
    price for but cannot charge them against the cap, so an unpriced model
    silently disables the one guard protecting the budget. Seeding happens
    before any call is made.
    """
    specs = specs if specs is not None else list(REGISTRY.values())
    seeded = []
    for sp in specs:
        meter.set_price(sp.model, sp.prompt_per_mtok, sp.completion_per_mtok)
        seeded.append(sp.model)
    return seeded


def estimated_plan_usd(specs: list[ModelSpec] | None = None) -> float:
    specs = specs if specs is not None else list(REGISTRY.values())
    return sum(sp.estimated_usd() for sp in specs)


def gold_repo_list(dest: Path | None = None,
                   source: Path | None = None) -> Path:
    """Write a repo_list.csv restricted to the gold studies.

    The corpus runner is driven by SRAF_REPO_LIST, so narrowing a run to the
    gold tier is a matter of handing it a shorter list rather than adding a
    code path that the full run does not exercise.
    """
    import csv
    source = source or REPO_ROOT / "validation" / "repo_list.csv"
    dest = dest or REPO_ROOT / "validation" / "repo_list_gold.csv"
    with open(source, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    keep = [r for r in rows if r.get("study_id") in set(GOLD_STUDIES)]
    missing = sorted(set(GOLD_STUDIES) - {r.get("study_id") for r in keep})
    if missing:
        raise ValueError(f"gold studies absent from {source}: {missing}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(keep)
    return dest
