"""Unit tests for the N3 frontier-model registry and its connectors.

None of these make a network call. They check the things that are cheap to get
wrong and expensive to discover during a paid run: that every spec is
well-formed, that prices actually reach the meter, that the gold subset is
exactly the gold tier, and that each backend routes to the right client.
"""
import csv

import pytest

from rag_pipeline.model_registry import (
    GOLD_STUDIES, REGISTRY, UNCONTAMINATED_CORPUS, ModelSpec,
    estimated_plan_usd, gold_repo_list, resolve, seed_prices,
)


def test_every_spec_is_well_formed():
    assert REGISTRY, "registry must not be empty"
    for key, sp in REGISTRY.items():
        assert sp.key == key
        assert sp.backend and sp.model and sp.key_env
        assert sp.prompt_per_mtok > 0 and sp.completion_per_mtok > 0
        assert sp.scope in ("corpus", "gold")
        assert sp.note, f"{key} must say why it exists"


def test_exactly_one_contaminated_and_it_is_excluded_from_the_headline():
    contaminated = [k for k, sp in REGISTRY.items() if sp.contaminated]
    assert contaminated == ["gemini-flash"]
    for k in contaminated:
        assert k not in UNCONTAMINATED_CORPUS


def test_uncontaminated_set_is_corpus_scope_only():
    for k in UNCONTAMINATED_CORPUS:
        assert REGISTRY[k].scope == "corpus"
        assert not REGISTRY[k].contaminated


def test_ceiling_probe_is_gold_scoped():
    assert REGISTRY["opus"].scope == "gold"
    assert REGISTRY["opus"].n_studies == len(GOLD_STUDIES) == 12


def test_resolve_selects_and_rejects():
    assert [sp.key for sp in resolve("grok,gpt5")] == ["grok", "gpt5"]
    assert len(resolve(None)) == len(REGISTRY)
    with pytest.raises(KeyError):
        resolve("no-such-model")


def test_plan_fits_the_budget():
    from rag_pipeline.model_registry import N3_BUDGET_USD
    est = estimated_plan_usd()
    assert est > 0
    assert est < N3_BUDGET_USD, (
        f"the declared plan estimates ${est:.2f} against a ${N3_BUDGET_USD:.2f} "
        "budget; either the prices or the budget need revisiting")


def test_ceiling_probe_is_cheaper_than_a_corpus_pass():
    """The probe exists to avoid paying for a fifth corpus pass."""
    opus = REGISTRY["opus"]
    sonnet = REGISTRY["sonnet"]
    assert opus.prompt_per_mtok > sonnet.prompt_per_mtok  # dearer per token
    assert opus.estimated_usd() < sonnet.estimated_usd()  # cheaper in total


def test_seed_prices_arms_the_cap():
    """An unpriced model is counted but not charged, which disables the guard."""
    class FakeMeter:
        def __init__(self):
            self.prices = {}

        def set_price(self, model, prompt_per_mtok, completion_per_mtok,
                      persist=True):
            self.prices[model] = (prompt_per_mtok, completion_per_mtok)

    m = FakeMeter()
    seeded = seed_prices(m, list(REGISTRY.values()))
    assert len(seeded) == len(REGISTRY)
    for sp in REGISTRY.values():
        assert m.prices[sp.model] == (sp.prompt_per_mtok, sp.completion_per_mtok)


def test_gold_repo_list_is_exactly_the_gold_tier(tmp_path):
    dest = gold_repo_list(dest=tmp_path / "gold.csv")
    with open(dest, newline="", encoding="utf-8") as fh:
        ids = [r["study_id"] for r in csv.DictReader(fh)]
    assert sorted(ids) == sorted(GOLD_STUDIES)


def test_estimated_usd_scales_with_scope():
    corpus = ModelSpec(key="x", backend="openai", model="m", key_env="K",
                       prompt_per_mtok=1.0, completion_per_mtok=1.0,
                       scope="corpus", note="n")
    gold = ModelSpec(key="y", backend="openai", model="m", key_env="K",
                     prompt_per_mtok=1.0, completion_per_mtok=1.0,
                     scope="gold", note="n")
    assert corpus.estimated_usd() > gold.estimated_usd()
    assert corpus.n_studies == 96 and gold.n_studies == 12


def test_backend_routing_for_the_new_providers(monkeypatch):
    from rag_pipeline.extractor import (
        AnthropicExtractor, OpenAICompatExtractor, get_extractor,
    )
    a = get_extractor("anthropic", model="claude-x", api_key="k")
    assert isinstance(a, AnthropicExtractor) and a.model == "claude-x"

    x = get_extractor("xai", model="grok-x", api_key="k")
    assert isinstance(x, OpenAICompatExtractor)
    assert "x.ai" in (x.base_url or "")

    # explicit overrides must win over the module-level globals, which is what
    # lets two hosted providers run inside one process
    c = get_extractor("compat", model="m", base_url="https://example.test/v1",
                      api_key="k2")
    assert c.base_url == "https://example.test/v1" and c.api_key == "k2"


def test_anthropic_requires_a_credential(monkeypatch):
    monkeypatch.setattr("rag_pipeline.extractor.ANTHROPIC_API_KEY", "")
    from rag_pipeline.extractor import get_extractor
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_extractor("anthropic", model="claude-x")
