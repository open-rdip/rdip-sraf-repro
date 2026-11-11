import pytest
from rag_pipeline.grounded import span_found, value_in_span, verify, summarise

PASSAGE = ("We train with a learning rate of 1e-4 and batch size 16 for 100 "
           "epochs on an NVIDIA A100 GPU. We set the random seed to 42. "
           "Our model reaches Sα = 77.0 on the test split.")


def test_verbatim_span_is_found():
    assert span_found("learning rate of 1e-4", PASSAGE)


def test_reflowed_and_typographic_variants_still_found():
    assert span_found("learning   rate\nof 1e-4", PASSAGE)
    assert span_found("We set the random seed to 42.", PASSAGE)


def test_invented_span_is_not_found():
    assert not span_found("we used three random seeds (1, 2, 3)", PASSAGE)
    assert not span_found("", PASSAGE)


def test_value_found_inside_its_own_evidence():
    assert value_in_span("16", "batch size 16 for 100 epochs")
    assert value_in_span("A100", "on an NVIDIA A100 GPU")


def test_numeric_formatting_is_not_a_grounding_failure():
    assert value_in_span("0.0001", "a learning rate of 1e-4")
    assert value_in_span(77.0, "Sα = 77.0 on the test split")


def test_value_absent_from_evidence_is_caught():
    assert not value_in_span("64", "batch size 16 for 100 epochs")


def test_fabricated_item_is_flagged_on_both_checks():
    ext = {"random_seeds": [{"value": "1234",
                             "evidence": "we used the seed 1234 throughout"}]}
    (r,) = verify(ext, PASSAGE)
    assert r["has_evidence"] and not r["span_found"] and r["value_in_span"]


def test_honest_item_passes_both():
    ext = {"random_seeds": [{"value": "42",
                             "evidence": "We set the random seed to 42."}]}
    (r,) = verify(ext, PASSAGE)
    assert r["span_found"] and r["value_in_span"]


def test_missing_evidence_is_not_silently_passed():
    ext = {"datasets": [{"name": "ImageNet"}]}
    (r,) = verify(ext, PASSAGE)
    assert not r["has_evidence"] and not r["span_found"]


def test_summary_counts_add_up():
    ext = {"hyperparameters": [
        {"name": "lr", "value": "1e-4", "evidence": "learning rate of 1e-4"},
        {"name": "bs", "value": "99", "evidence": "batch size 99 was used"}]}
    s = summarise(verify(ext, PASSAGE))
    assert s["total"]["n"] == 2
    assert s["total"]["grounded"] == 1


def test_local_model_slug_agrees_with_the_pipeline_copy():
    """`grounded.model_slug` is a deliberate copy of the pipeline's, so that a
    cluster job need not import the triplestore client for a regex. If the two
    ever diverge, every grounded output filename stops lining up with its
    ungrounded counterpart and the comparison in paper_notes AE.4 breaks
    silently. Pin them together.
    """
    import re
    from rag_pipeline.grounded import model_slug

    def reference(model):
        return re.sub(r"-+", "-",
                      re.sub(r"[^a-z0-9]+", "-",
                             (model or "default").lower())).strip("-")

    cases = [
        "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8",
        "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8",
        "RedHatAI/Mistral-Small-24B-Instruct-2501-quantized.w8a8",
        "claude-opus-5-5", "gpt-5", "grok-4.7", "gemini-3.8-flash",
        None, "", "---", "A..B__C",
    ]
    for m in cases:
        assert model_slug(m) == reference(m), m


def test_open_weight_slugs_match_the_existing_ungrounded_filenames():
    """The three open-weight checkpoints already have a full ungrounded corpus
    pass on disk. The grounded run must write slugs that match, or AE.4's
    before/after comparison silently compares nothing.
    """
    from rag_pipeline.grounded import model_slug
    from rag_pipeline.model_registry import REGISTRY, OPEN_WEIGHTS

    expected = {
        "qwen": "qwen-qwen2-5-14b-instruct-gptq-int8",
        "llama": "redhatai-meta-llama-3-1-8b-instruct-quantized-w8a8",
        "mistral": "redhatai-mistral-small-24b-instruct-2501-quantized-w8a8",
    }
    assert set(OPEN_WEIGHTS) == set(expected)
    for key, slug in expected.items():
        assert REGISTRY[key].backend == "vllm"
        assert model_slug(REGISTRY[key].model) == slug


# ── fuzzy span: telling paraphrase apart from invention ─────────────────────

_PASSAGE = (
    "We train the model with a batch size of 256 and a learning rate of 3e-4 "
    "on eight NVIDIA A100 GPUs, using the AdamW optimiser and a cosine "
    "schedule. All runs use seed 1234."
)


def _verdict(evidence):
    from rag_pipeline.grounded import fuzzy_span
    lo, tr = fuzzy_span(evidence, _PASSAGE)
    if lo >= 0.60:
        return "near_verbatim"
    return "paraphrase" if tr >= 0.70 else "unsupported"


def test_reflowed_quote_reads_as_near_verbatim():
    """A model that copies correctly but reflows the line break must not be
    counted as fabricating."""
    assert _verdict("batch size of 256 and a\n   learning rate of 3e-4") == "near_verbatim"


def test_paraphrase_is_not_called_fabrication():
    """The failure mode that would wreck the Llama claim: a small model that
    restates rather than quotes. Same vocabulary, different wording."""
    assert _verdict("the batch size was 256 with learning rate 3e-4") == "paraphrase"


def test_invention_is_flagged_unsupported():
    assert _verdict("we set dropout to 0.5 and used label smoothing of 0.1") == "unsupported"


def test_plausible_invention_is_flagged_unsupported():
    """Invented content that reads like a methods sentence but shares no
    vocabulary with the source. This is the case the exact check already
    catches and the fuzzy check must not rescue."""
    assert _verdict("trained on sixteen TPU v4 pods for ninety epochs") == "unsupported"


def test_fuzzy_span_is_bounded_and_safe_on_empty_input():
    from rag_pipeline.grounded import fuzzy_span
    for ev, pa in [("", _PASSAGE), (_PASSAGE, ""), ("", "")]:
        assert fuzzy_span(ev, pa) == (0.0, 0.0)
    lo, tr = fuzzy_span(_PASSAGE, _PASSAGE)
    assert lo == 1.0 and tr == 1.0


def test_verify_adds_fuzzy_fields_only_to_span_misses():
    """The new fields must not appear on the common path, so that the four
    frontier runs already on disk stay comparable to anything run later.
    """
    from rag_pipeline.grounded import verify
    ex = {"hyperparameters": [
        {"name": "batch_size", "value": "256",
         "evidence": "a batch size of 256"},                       # verbatim
        {"name": "dropout", "value": "0.5",
         "evidence": "we set dropout to 0.5 and used label smoothing"},  # not there
    ]}
    recs = verify(ex, _PASSAGE)
    hit = [r for r in recs if r["span_found"]]
    miss = [r for r in recs if not r["span_found"]]
    assert len(hit) == 1 and len(miss) == 1
    assert "fuzzy_longest" not in hit[0]
    assert miss[0]["fuzzy_longest"] >= 0.0
    assert miss[0]["fuzzy_token_recall"] >= 0.0


def test_summarise_classifies_every_span_miss():
    from rag_pipeline.grounded import verify, summarise
    ex = {"hyperparameters": [
        {"name": "a", "value": "256", "evidence": "a batch size of 256"},
        {"name": "b", "value": "3e-4",
         "evidence": "the batch size was 256 with learning rate 3e-4"},
        {"name": "c", "value": "0.5",
         "evidence": "we set dropout to 0.5 and label smoothing of 0.1"},
    ]}
    tot = summarise(verify(ex, _PASSAGE))["total"]
    misses = (tot.get("miss_near_verbatim", 0) + tot.get("miss_paraphrase", 0)
              + tot.get("miss_unsupported", 0) + tot.get("miss_unscored", 0))
    assert misses == tot["n"] - tot["span_found"], \
        "every span miss must land in exactly one bucket"


def test_unscored_misses_are_not_reported_as_fabrication():
    """Output written before fuzzy scoring existed carries no fuzzy fields.
    Re-summarising it must say 'not measured', never 'unsupported', or the
    four frontier runs already on disk would appear to show fabrication that
    was never tested for.
    """
    from rag_pipeline.grounded import summarise
    legacy = [{"field": "hyperparameters", "value": "0.5", "evidence": "not in passage",
               "has_evidence": True, "span_found": False, "value_in_span": False}]
    tot = summarise(legacy)["total"]
    assert tot.get("miss_unscored") == 1
    assert tot.get("miss_unsupported", 0) == 0
