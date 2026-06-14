"""Unit tests for the multi-backend LLM extractor abstraction."""
import pytest

from rag_pipeline.extractor import (
    get_extractor, _parse_json, merge_extractions,
    Extractor, OpenAICompatExtractor, GeminiExtractor,
)


def test_backend_routing():
    assert isinstance(get_extractor("openai"), OpenAICompatExtractor)
    v = get_extractor("vllm", model="Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8")
    assert isinstance(v, OpenAICompatExtractor)
    assert v.base_url.endswith("/v1")
    assert v.model == "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int8"
    assert isinstance(get_extractor("google"), GeminiExtractor)
    with pytest.raises(ValueError):
        get_extractor("nonexistent")


@pytest.mark.parametrize("raw,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('here you go: {"a": 1} done', {"a": 1}),
    ('{"a": [1, 2', {"a": [1, 2]}),     # truncated -> auto-closed
    ('', {}),
    ('no json at all', {}),
])
def test_parse_json(raw, expected):
    assert _parse_json(raw) == expected


def test_extract_with_stub_backend():
    class Stub(Extractor):
        name = "stub"
        def _complete(self, system, user):
            return '{"random_seeds": [42], "methods": []}'
    assert Stub().extract("passage")["random_seeds"] == [42]


def test_extract_returns_empty_on_backend_error():
    class Boom(Extractor):
        def _complete(self, system, user):
            raise RuntimeError("server down")
    assert Boom().extract("passage") == {}


def test_merge_dedup_and_union():
    a = {"dependencies": [{"name": "torch", "version": "2.0"}],
         "random_seeds": [42], "hardware": {"gpu_model": "A100"},
         "hyperparameters": [], "datasets": [], "methods": []}
    b = {"dependencies": [{"name": "torch", "version": "2.1"}],
         "random_seeds": [42, 7], "hardware": {"cuda_version": "12.1"},
         "hyperparameters": [{"name": "lr", "value": "0.1"}],
         "datasets": [], "methods": []}
    m = merge_extractions([a, b])
    assert len(m["dependencies"]) == 1                 # torch de-duplicated
    assert sorted(m["random_seeds"]) == [7, 42]        # union
    assert m["hardware"]["gpu_model"] == "A100"
    assert m["hardware"]["cuda_version"] == "12.1"     # filled from b
    assert len(m["hyperparameters"]) == 1
