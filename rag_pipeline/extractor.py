"""LLM extraction of reproducibility metadata — one interface, several backends.

Backends (selected via config.LLM_BACKEND), all returning the same JSON schema:
  openai   -> OpenAI API (e.g. GPT-4o)             OpenAI-compatible
  vllm     -> local vLLM OpenAI server (cluster)   OpenAI-compatible
  llamacpp -> local llama.cpp OpenAI server (Mac)  OpenAI-compatible
  google   -> Google Gemini

The three OpenAI-compatible backends share one implementation pointed at
different base URLs, which is exactly how vLLM serves the open-weights models —
so multi-model comparison is just get_extractor("vllm", model=<repo>).

Public API (kept stable for rag_pipeline.pipeline):
  extract_metadata(passage, backend=None, model=None) -> dict
  merge_extractions(list[dict]) -> dict
"""
from __future__ import annotations
import json
import os
import re
import time
from abc import ABC, abstractmethod

from config import (
    LLM_BACKEND, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS,
    OPENAI_API_KEY, GOOGLE_API_KEY, VLLM_SERVER_URL, LLAMACPP_SERVER_URL,
)

# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a scientific metadata extractor specialising in
computational reproducibility. Extract structured metadata from research
paper passages. Return ONLY valid JSON — no markdown, no explanation,
no code blocks."""

EXTRACTION_PROMPT = """Extract all reproducibility-critical metadata from
the passage below. Return a JSON object with EXACTLY this structure:

{{
  "dependencies": [{{"name": "string", "version": "string"}}],
  "random_seeds": [integer],
  "hardware": {{
    "gpu_model": "string or null",
    "cuda_version": "string or null",
    "cpu_info": "string or null"
  }},
  "hyperparameters": [{{"name": "string", "value": "string"}}],
  "datasets": [{{"name": "string", "version": "string or null"}}],
  "methods": [{{"name": "string", "description": "string"}}],
  "evaluation_results": [{{"metric": "string", "value": "string", "split": "string or null"}}]
}}

Rules:
- Use null for absent scalar fields, [] for absent arrays
- Extract version numbers exactly as written
- Only extract integer random seeds that are explicitly stated
- For evaluation_results, extract each reported metric with its exact reported
  value and the split it was measured on (train / validation / test) if stated
- Do not invent values not present in the text

Passage:
{passage}"""


# ── Backends ──────────────────────────────────────────────────────────────────

class Extractor(ABC):
    """Abstract extractor: subclasses implement _complete(system, user) -> str."""

    name = "extractor"

    @abstractmethod
    def _complete(self, system: str, user: str) -> str:
        ...

    def extract(self, passage: str) -> dict:
        try:
            raw = self._complete(SYSTEM_PROMPT, EXTRACTION_PROMPT.format(passage=passage))
            return _parse_json(raw)
        except Exception as e:  # noqa: BLE001
            print(f"[Extractor:{self.name}] Error: {e}")
            return {}


class OpenAICompatExtractor(Extractor):
    """Any OpenAI-compatible chat endpoint: OpenAI API, vLLM, or llama.cpp."""

    def __init__(self, base_url: str | None, api_key: str, model: str, name: str):
        self.base_url = base_url
        self.api_key = api_key or "EMPTY"
        self.model = model
        self.name = name
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI  # lazy: only needed when actually calling
            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        return self._client

    def _complete(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content


class GeminiExtractor(Extractor):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key
        self.name = "gemini"

    def _complete(self, system: str, user: str) -> str:
        import google.generativeai as genai  # lazy
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model, system_instruction=system)
        for attempt in range(3):
            try:
                resp = model.generate_content(
                    user,
                    generation_config=genai.GenerationConfig(
                        temperature=LLM_TEMPERATURE,
                        max_output_tokens=max(LLM_MAX_TOKENS, 4096),
                    ),
                )
                return resp.text
            except Exception as e:  # noqa: BLE001 — handle Gemini rate limits
                msg = str(e)
                if "429" in msg and attempt < 2:
                    m = re.search(r"seconds:\s*(\d+)", msg)
                    wait = (int(m.group(1)) + 5) if m else 30
                    print(f"[Extractor:gemini] rate limited — waiting {wait}s")
                    time.sleep(wait)
                else:
                    raise
        return "{}"


def get_extractor(backend: str | None = None, model: str | None = None) -> Extractor:
    """Build an extractor for the given (or configured) backend."""
    backend = (backend or LLM_BACKEND).lower()
    model = model or LLM_MODEL

    if backend == "openai":
        return OpenAICompatExtractor(None, OPENAI_API_KEY, model, "openai")
    if backend == "vllm":
        return OpenAICompatExtractor(
            VLLM_SERVER_URL.rstrip("/") + "/v1", "EMPTY", model, "vllm")
    if backend == "llamacpp":
        return OpenAICompatExtractor(
            LLAMACPP_SERVER_URL.rstrip("/") + "/v1", "EMPTY", model, "llamacpp")
    if backend in ("google", "gemini"):
        return GeminiExtractor(model, GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY", ""))
    raise ValueError(f"Unknown LLM backend: {backend!r}")


# ── JSON parser ───────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    """Robustly parse LLM output to JSON (handles code fences, truncation)."""
    if not raw:
        return {}
    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    if "{" in raw:  # try to close a truncated object
        truncated = raw[raw.index("{"):]
        closing = ("]" * (truncated.count("[") - truncated.count("]")) +
                   "}" * (truncated.count("{") - truncated.count("}")))
        try:
            return json.loads(truncated + closing)
        except json.JSONDecodeError:
            pass
    print(f"[Extractor] WARNING: could not parse JSON from: {raw[:200]}")
    return {}


# ── Public API (stable for the pipeline) ──────────────────────────────────────

_DEFAULT: Extractor | None = None


def extract_metadata(passage: str, backend: str | None = None,
                     model: str | None = None) -> dict:
    """Extract reproducibility metadata from a passage via the chosen backend."""
    global _DEFAULT
    if backend or model:
        return get_extractor(backend, model).extract(passage)
    if _DEFAULT is None:
        _DEFAULT = get_extractor()
    return _DEFAULT.extract(passage)


def merge_extractions(extractions: list[dict]) -> dict:
    """Merge per-chunk extractions, de-duplicating by name within each category."""
    merged = {
        "dependencies": [], "random_seeds": [],
        "hardware": {"gpu_model": None, "cuda_version": None, "cpu_info": None},
        "hyperparameters": [], "datasets": [], "methods": [],
        "evaluation_results": [],
    }
    seen_deps, seen_params, seen_datasets, seen_evals = set(), set(), set(), set()

    for ext in extractions:
        if not ext:
            continue
        for dep in ext.get("dependencies", []):
            key = dep.get("name", "").lower()
            if key and key not in seen_deps:
                merged["dependencies"].append(dep); seen_deps.add(key)
        for seed in ext.get("random_seeds", []):
            if isinstance(seed, int) and seed not in merged["random_seeds"]:
                merged["random_seeds"].append(seed)
        hw = ext.get("hardware", {}) or {}
        for field in ("gpu_model", "cuda_version", "cpu_info"):
            if hw.get(field) and not merged["hardware"][field]:
                merged["hardware"][field] = hw[field]
        for param in ext.get("hyperparameters", []):
            key = param.get("name", "").lower()
            if key and key not in seen_params:
                merged["hyperparameters"].append(param); seen_params.add(key)
        for ds in ext.get("datasets", []):
            key = ds.get("name", "").lower()
            if key and key not in seen_datasets:
                merged["datasets"].append(ds); seen_datasets.add(key)
        for method in ext.get("methods", []):
            if method not in merged["methods"]:
                merged["methods"].append(method)
        for ev in ext.get("evaluation_results", []):
            metric = (ev.get("metric") or "").lower()
            key = (metric, (ev.get("split") or "").lower())
            if metric and key not in seen_evals:
                merged["evaluation_results"].append(ev); seen_evals.add(key)
    return merged
