"""LLM extraction of reproducibility metadata — one interface, several backends.

Backends (selected via config.LLM_BACKEND), all returning the same JSON schema:
  openai    -> OpenAI API (e.g. GPT-5)              OpenAI-compatible
  compat    -> any hosted OpenAI-compatible endpoint (SRAF_COMPAT_BASE_URL)
  xai       -> xAI / Grok                           OpenAI-compatible
  vllm      -> local vLLM OpenAI server (cluster)   OpenAI-compatible
  llamacpp  -> local llama.cpp OpenAI server (Mac)  OpenAI-compatible
  google    -> Google Gemini
  anthropic -> Anthropic Messages API (its own schema)

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
    OPENAI_BASE_URL, COMPAT_BASE_URL, COMPAT_API_KEY, LLM_BUDGET_USD,
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, XAI_API_KEY, XAI_BASE_URL,
)
from rag_pipeline.usage_meter import meter, BudgetExceeded

if LLM_BUDGET_USD:
    meter.configure(budget_usd=LLM_BUDGET_USD)

# Which study the current extraction belongs to, so the meter can attribute
# cost per study (the input contribution N7 needs). The corpus runner sets it;
# ad-hoc callers can ignore it.
_CURRENT_STUDY: str | None = None


def set_study(study_id: str | None) -> None:
    """Attribute subsequent completions to this study in the usage meter."""
    global _CURRENT_STUDY
    _CURRENT_STUDY = study_id

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
        except BudgetExceeded:
            # Must propagate. Swallowing this would leave the loop calling a paid
            # endpoint for every remaining chunk with the cap already breached.
            raise
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
        # Capabilities discovered from the provider's own 400s on the first
        # call, then reused. The N3 set spans five providers and two model
        # generations, and the newer OpenAI models reject parameters the older
        # ones require, so the shape of a valid request is not knowable from
        # the model name alone.
        self._token_param = "max_tokens"
        self._accepts_temperature = True
        self._accepts_response_format = True
        self._accepts_reasoning_effort = True

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI  # lazy: only needed when actually calling
            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        return self._client

    #: Reasoning models count reasoning tokens against max_completion_tokens,
    #: so the output budget is whatever deliberation leaves behind. At
    #: LLM_MAX_TOKENS=2000 gpt-5 averaged 1760 completion tokens per call and
    #: returned empty arrays for every field after `methods`: it ran out of
    #: allowance mid-object. Extraction is not a task that benefits from long
    #: deliberation, so we ask for low effort and give the budget headroom.
    REASONING_TOKEN_FLOOR = 16000

    def _build_kwargs(self, system: str, user: str) -> dict:
        reasoning = self._token_param == "max_completion_tokens"
        budget = (max(LLM_MAX_TOKENS, self.REASONING_TOKEN_FLOOR)
                  if reasoning else LLM_MAX_TOKENS)
        kwargs = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            self._token_param: budget,
        }
        if reasoning and self._accepts_reasoning_effort:
            kwargs["reasoning_effort"] = "low"
        if self._accepts_temperature:
            kwargs["temperature"] = LLM_TEMPERATURE
        if self._accepts_response_format:
            kwargs["response_format"] = {"type": "json_object"}
        return kwargs

    def _adapt(self, err: str) -> bool:
        """Drop or rename one parameter the provider just rejected.

        Returns True if something changed and the call is worth retrying. Each
        adaptation is announced, because two of them change what the request
        means rather than just its spelling: losing response_format weakens the
        JSON guarantee, and losing temperature means the completion samples at
        the provider default instead of at LLM_TEMPERATURE. Silent degradation
        here would put an unrecorded difference between the models N3 compares.
        """
        if "max_completion_tokens" in err and self._token_param == "max_tokens":
            self._token_param = "max_completion_tokens"
            print(f"[Extractor:{self.name}] uses max_completion_tokens, switching")
            return True
        if "response_format" in err and self._accepts_response_format:
            self._accepts_response_format = False
            print(f"[Extractor:{self.name}] response_format unsupported, "
                  "retrying without it (prompt still demands bare JSON)")
            return True
        if "reasoning_effort" in err and self._accepts_reasoning_effort:
            self._accepts_reasoning_effort = False
            print(f"[Extractor:{self.name}] reasoning_effort unsupported, "
                  "retrying without it")
            return True
        if "temperature" in err and self._accepts_temperature:
            self._accepts_temperature = False
            print(f"[Extractor:{self.name}] WARNING: this model rejects "
                  f"temperature, so these completions run at the provider "
                  f"default rather than at LLM_TEMPERATURE={LLM_TEMPERATURE}. "
                  "Report this asymmetry.")
            return True
        return False

    def _complete(self, system: str, user: str) -> str:
        resp = None
        for _ in range(4):
            try:
                resp = self.client.chat.completions.create(
                    **self._build_kwargs(system, user))
                break
            except BudgetExceeded:
                raise
            except Exception as e:  # noqa: BLE001
                if not self._adapt(str(e)):
                    raise
        if resp is None:
            raise RuntimeError(
                f"{self.name}: no accepted request shape after adaptation")

        usage = getattr(resp, "usage", None)
        if usage is not None:
            meter.record(
                self.model,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                study=_CURRENT_STUDY,
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
                um = getattr(resp, "usage_metadata", None)
                if um is not None:
                    meter.record(
                        self.model,
                        prompt_tokens=getattr(um, "prompt_token_count", 0) or 0,
                        completion_tokens=getattr(um, "candidates_token_count", 0) or 0,
                        study=_CURRENT_STUDY,
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


class AnthropicExtractor(Extractor):
    """Anthropic Messages API.

    The only provider in the N3 set that is not OpenAI-compatible, so it gets
    its own client rather than being bent into the shared one. Two details
    matter for extraction quality and are deliberate:

    * `system` is a top-level parameter, not a message with role "system".
    * The assistant turn is prefilled with "{" so the model continues a JSON
      object instead of opening with prose. The opening brace is put back on
      the response before parsing. This removes most of the "here is the JSON"
      preamble that otherwise has to be stripped heuristically.
    """

    #: Set once, the first time a completion runs on an SDK with no sampling
    #: control, so the warning is printed per process rather than per call.
    _warned_no_temperature = False

    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.name = "anthropic"
        self._client = None
        self._accepts_temperature = False

    @property
    def client(self):
        if self._client is None:
            from anthropic import Anthropic  # lazy: only when actually calling
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = Anthropic(**kwargs)
            self._accepts_temperature = self._probe_temperature(self._client)
        return self._client

    @staticmethod
    def _probe_temperature(client) -> bool:
        """Does this SDK's messages.create accept a temperature argument?

        Checked by signature inspection, not by making a call, so it costs
        nothing. The answer matters beyond convenience: every other backend in
        this registry is pinned to LLM_TEMPERATURE (0.0), and if Anthropic
        cannot be, its passes sample at the provider default while the others
        do not. That asymmetry is reported rather than absorbed, so it is
        recorded here instead of being worked around silently.

        As of anthropic 2.x, messages.create exposes neither temperature nor
        top_p nor top_k, and output_config carries only `effort` and `format`.
        There is no sampling control to set.
        """
        import inspect
        try:
            params = inspect.signature(client.messages.create).parameters
        except (TypeError, ValueError):
            return False
        return "temperature" in params

    def _complete(self, system: str, user: str) -> str:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                call = dict(
                    model=self.model,
                    max_tokens=max(LLM_MAX_TOKENS, 4096),
                    system=system,
                )
                if self._accepts_temperature:
                    call["temperature"] = LLM_TEMPERATURE
                elif not AnthropicExtractor._warned_no_temperature:
                    AnthropicExtractor._warned_no_temperature = True
                    print("[extractor] WARNING: this anthropic SDK exposes no "
                          "sampling control, so these completions run at the "
                          "provider default rather than at "
                          f"LLM_TEMPERATURE={LLM_TEMPERATURE}. Every other "
                          "backend is pinned. Report this asymmetry.")
                # No assistant prefill. Models of this generation reject it
                # ("This model does not support assistant message prefill"),
                # and _parse_json already tolerates fences and preamble, which
                # is what the prefill was avoiding rather than requiring.
                resp = self.client.messages.create(
                    **call,
                    messages=[{"role": "user", "content": user}],
                )
                usage = getattr(resp, "usage", None)
                if usage is not None:
                    meter.record(
                        self.model,
                        prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
                        completion_tokens=getattr(usage, "output_tokens", 0) or 0,
                        study=_CURRENT_STUDY,
                    )
                text = "".join(
                    getattr(b, "text", "") for b in (resp.content or [])
                    if getattr(b, "type", "") == "text")
                return text
            except BudgetExceeded:
                raise
            except Exception as e:  # noqa: BLE001 — retry transient overload
                last_err = e
                msg = str(e)
                transient = any(code in msg for code in ("429", "500", "502", "503", "529"))
                if transient and attempt < 2:
                    wait = 5 * (2 ** attempt)
                    print(f"[Extractor:anthropic] transient error, waiting {wait}s: {msg[:120]}")
                    time.sleep(wait)
                    continue
                raise
        if last_err:
            raise last_err
        return "{}"


def get_extractor(backend: str | None = None, model: str | None = None,
                  base_url: str | None = None,
                  api_key: str | None = None) -> Extractor:
    """Build an extractor for the given (or configured) backend.

    `base_url` and `api_key` override whatever the environment supplies. The
    model registry passes them explicitly so that several hosted providers can
    run in one process: the module-level COMPAT_* settings are global and can
    only describe one endpoint at a time.
    """
    backend = (backend or LLM_BACKEND).lower()
    model = model or LLM_MODEL

    if backend == "openai":
        return OpenAICompatExtractor(
            base_url or OPENAI_BASE_URL, api_key or OPENAI_API_KEY, model, "openai")
    if backend in ("compat", "openai_compat"):
        # Generic hosted provider: anything serving an OpenAI-compatible chat
        # endpoint. Point SRAF_COMPAT_BASE_URL / SRAF_COMPAT_API_KEY at it.
        # Kept provider-agnostic on purpose, so adding a frontier model for N3
        # never means shipping a new client.
        url = base_url or COMPAT_BASE_URL
        if not url:
            raise ValueError(
                "backend 'openai_compat' needs a base_url argument or "
                "SRAF_COMPAT_BASE_URL (and usually SRAF_COMPAT_API_KEY)")
        return OpenAICompatExtractor(
            url, api_key or COMPAT_API_KEY, model, "compat")
    if backend in ("xai", "grok"):
        key = api_key or XAI_API_KEY
        if not key:
            raise ValueError("backend 'xai' needs XAI_API_KEY")
        return OpenAICompatExtractor(
            base_url or XAI_BASE_URL, key, model, "xai")
    if backend in ("anthropic", "claude"):
        key = api_key or ANTHROPIC_API_KEY
        if not key:
            raise ValueError("backend 'anthropic' needs ANTHROPIC_API_KEY")
        return AnthropicExtractor(model, key, base_url or ANTHROPIC_BASE_URL)
    if backend == "vllm":
        return OpenAICompatExtractor(
            VLLM_SERVER_URL.rstrip("/") + "/v1", "EMPTY", model, "vllm")
    if backend == "llamacpp":
        return OpenAICompatExtractor(
            LLAMACPP_SERVER_URL.rstrip("/") + "/v1", "EMPTY", model, "llamacpp")
    if backend in ("google", "gemini"):
        return GeminiExtractor(
            model, api_key or GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY", ""))
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
                     model: str | None = None, base_url: str | None = None,
                     api_key: str | None = None) -> dict:
    """Extract reproducibility metadata from a passage via the chosen backend."""
    global _DEFAULT
    if backend or model or base_url or api_key:
        return get_extractor(backend, model, base_url, api_key).extract(passage)
    if _DEFAULT is None:
        _DEFAULT = get_extractor()
    return _DEFAULT.extract(passage)


# Models frequently emit these as a *string* where they mean "absent"; treat
# them as null so they don't become spurious values/triples.
_NULLISH = {"", "null", "none", "n/a", "na", "nan", "nil",
            "unknown", "not specified", "not reported", "not stated"}


def _clean(v):
    """Coerce model-emitted nullish strings (e.g. the literal "null") to None."""
    if isinstance(v, str) and v.strip().lower() in _NULLISH:
        return None
    return v


def _key(name) -> str:
    """Lowercased identity key for an item; '' for nullish/absent names."""
    c = _clean(name)
    return c.strip().lower() if isinstance(c, str) else ""


def merge_extractions(extractions: list[dict]) -> dict:
    """Merge per-chunk extractions, de-duplicating by name within each category.
    Nullish strings ("null", "n/a", …) are normalised to None throughout."""
    merged = {
        "dependencies": [], "random_seeds": [],
        "hardware": {"gpu_model": None, "cuda_version": None, "cpu_info": None},
        "hyperparameters": [], "datasets": [], "methods": [],
        "evaluation_results": [],
    }
    seen_deps, seen_params, seen_datasets, seen_evals, seen_methods = (
        set(), set(), set(), set(), set())

    for ext in extractions:
        if not ext:
            continue
        for dep in ext.get("dependencies", []):
            key = _key(dep.get("name"))
            if key and key not in seen_deps:
                merged["dependencies"].append(
                    {"name": dep.get("name"), "version": _clean(dep.get("version"))})
                seen_deps.add(key)
        for seed in ext.get("random_seeds", []):
            if isinstance(seed, int) and seed not in merged["random_seeds"]:
                merged["random_seeds"].append(seed)
        hw = ext.get("hardware", {}) or {}
        for field in ("gpu_model", "cuda_version", "cpu_info"):
            val = _clean(hw.get(field))
            if val and not merged["hardware"][field]:
                merged["hardware"][field] = val
        for param in ext.get("hyperparameters", []):
            key = _key(param.get("name"))
            if key and key not in seen_params:
                merged["hyperparameters"].append(
                    {"name": param.get("name"), "value": _clean(param.get("value"))})
                seen_params.add(key)
        for ds in ext.get("datasets", []):
            key = _key(ds.get("name"))
            if key and key not in seen_datasets:
                merged["datasets"].append(
                    {"name": ds.get("name"), "version": _clean(ds.get("version"))})
                seen_datasets.add(key)
        for method in ext.get("methods", []):
            key = _key(method.get("name") if isinstance(method, dict) else method)
            if key and key not in seen_methods:
                merged["methods"].append(method); seen_methods.add(key)
        for ev in ext.get("evaluation_results", []):
            metric = _key(ev.get("metric"))
            split = (_clean(ev.get("split")) or "")
            key = (metric, split.lower())
            if metric and key not in seen_evals:
                merged["evaluation_results"].append(
                    {"metric": ev.get("metric"), "value": _clean(ev.get("value")),
                     "split": _clean(ev.get("split"))})
                seen_evals.add(key)
    return merged
