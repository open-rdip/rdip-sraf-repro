"""
Sends retrieved passages to an LLM and extracts structured
reproducibility metadata as JSON.

Supports:
  - Google Gemini (default for testing)
  - OpenAI GPT-4o
"""


import time
import json
import os
import re
import time
from dotenv import load_dotenv

load_dotenv()

BACKEND   = os.getenv("LLM_BACKEND", "google")
MODEL     = os.getenv("LLM_MODEL",   "gemini-2.0-flash")

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
  "methods": [{{"name": "string", "description": "string"}}]
}}

Rules:
- Use null for absent scalar fields, [] for absent arrays
- Extract version numbers exactly as written
- Only extract integer random seeds that are explicitly stated
- Do not invent values not present in the text

Passage:
{passage}"""

# ── Google Gemini backend ─────────────────────────────────────────────────────

def _extract_google(passage: str) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    response = model.generate_content(
        EXTRACTION_PROMPT.format(passage=passage),
        generation_config=genai.GenerationConfig(
            temperature=0.0,
            max_output_tokens=4096,
        )
    )

    raw = response.text.strip()
    return _parse_json(raw)


# ── OpenAI backend ────────────────────────────────────────────────────────────

def _extract_openai(passage: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system",  "content": SYSTEM_PROMPT},
            {"role": "user",    "content": EXTRACTION_PROMPT.format(passage=passage)},
        ],
        temperature=0.0,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    return _parse_json(response.choices[0].message.content)


# ── JSON parser ───────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    """
    Robustly parse LLM output to JSON.
    Handles markdown code fences, truncated responses,
    and minor formatting issues.
    """
    # Strip markdown code fences
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    raw = raw.strip("`").strip()

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to find and parse a complete { ... } block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Handle truncated JSON — try to close it
    if "{" in raw:
        truncated = raw[raw.index("{"):]
        # Count unclosed braces and brackets
        open_braces   = truncated.count("{") - truncated.count("}")
        open_brackets = truncated.count("[") - truncated.count("]")
        # Close them
        closing = ("]" * open_brackets) + ("}" * open_braces)
        try:
            return json.loads(truncated + closing)
        except json.JSONDecodeError:
            pass

    print(f"[Extractor] WARNING: could not parse JSON from: {raw[:200]}")
    return {}


# ── Main entry point ─────────────────────────────────────────────────────────

def extract_metadata(passage: str) -> dict:
    """
    Extract reproducibility metadata from a text passage.
    Routes to the configured LLM backend.
    """
    try:
        if BACKEND == "google":
            return _extract_google(passage)
        elif BACKEND == "openai":
            return _extract_openai(passage)
        else:
            raise ValueError(f"Unknown LLM backend: {BACKEND}")
    except Exception as e:
        print(f"[Extractor] Error: {e}")
        return {}


def merge_extractions(extractions: list[dict]) -> dict:
    """
    Merge results from multiple chunk extractions.
    Deduplicates by name field within each category.
    """
    merged = {
        "dependencies":   [],
        "random_seeds":   [],
        "hardware":       {"gpu_model": None, "cuda_version": None, "cpu_info": None},
        "hyperparameters":[],
        "datasets":       [],
        "methods":        [],
    }

    seen_deps   = set()
    seen_params = set()
    seen_datasets = set()

    for ext in extractions:
        if not ext:
            continue

        for dep in ext.get("dependencies", []):
            key = dep.get("name", "").lower()
            if key and key not in seen_deps:
                merged["dependencies"].append(dep)
                seen_deps.add(key)

        for seed in ext.get("random_seeds", []):
            if isinstance(seed, int) and seed not in merged["random_seeds"]:
                merged["random_seeds"].append(seed)

        hw = ext.get("hardware", {})
        for field in ["gpu_model", "cuda_version", "cpu_info"]:
            if hw.get(field) and not merged["hardware"][field]:
                merged["hardware"][field] = hw[field]

        for param in ext.get("hyperparameters", []):
            key = param.get("name", "").lower()
            if key and key not in seen_params:
                merged["hyperparameters"].append(param)
                seen_params.add(key)

        for ds in ext.get("datasets", []):
            key = ds.get("name", "").lower()
            if key and key not in seen_datasets:
                merged["datasets"].append(ds)
                seen_datasets.add(key)

        for method in ext.get("methods", []):
            if method not in merged["methods"]:
                merged["methods"].append(method)

    return merged

def _extract_google(passage: str) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    for attempt in range(3):
        try:
            response = model.generate_content(
                EXTRACTION_PROMPT.format(passage=passage),
                generation_config=genai.GenerationConfig(
                    temperature=0.0,
                    max_output_tokens=4096,
                )
            )
            return _parse_json(response.text.strip())

        except Exception as e:
            error_str = str(e)
            if "429" in error_str and "retry_delay" in error_str:
                # Extract suggested wait time from error message
                import re
                m = re.search(r"seconds:\s*(\d+)", error_str)
                wait = int(m.group(1)) + 5 if m else 60
                print(f"[Extractor] Rate limited — waiting {wait}s "
                      f"(attempt {attempt+1}/3) ...")
                time.sleep(wait)
            else:
                print(f"[Extractor] Error: {e}")
                return {}

    print("[Extractor] Max retries exceeded — skipping passage")
    return {}
