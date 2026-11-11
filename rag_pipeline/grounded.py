"""Span-grounded extraction: a pilot that makes precision measurable.

Why this exists
---------------
The production extractor returns a list of values. Scoring it means comparing
those strings against a reference list, and on this corpus that turned out not
to measure extraction quality at all (paper_notes AD): the reference is itself
single-generator output with an estimated 47-64% recall, so a correct
extraction the reference lacks is scored as a false positive. Eight models from
seven organisations agree with each other 3.7x more than any agrees with the
reference.

The fix is not a better matcher. We tried that: value normalisation moved the
model-to-reference ratio not at all. The fix is to change what an extracted
item *is*.

Here every item carries the verbatim passage text it came from. That buys three
things the list form cannot:

1. **Precision without a reference.** "Does this span support this value" is a
   local question. It needs no gold list, so it can be asked on every study
   rather than on the twelve that happen to have one.
2. **Identity by span rather than by string.** Two models citing the same
   sentence are extracting the same fact whether they write "Sa" or "S_alpha".
   The matching problem dissolves instead of being patched.
3. **Fabrication becomes demonstrable.** A claim whose quoted evidence does not
   occur in the source is invented, and that is checkable by string search with
   no model and no cost. Llama's 52-of-95 seed claims are currently inferred
   from disagreement; this turns the inference into a measurement.

Two checks run free and deterministically over every item:

    span_found    the quoted evidence really occurs in the passage
    value_in_span the extracted value occurs inside that quote

Neither proves the claim is *true* — a span can be real and still not support
the reading placed on it — so a human sample remains necessary for the third
level. But these two bound the problem from below at zero marginal cost, and
they are what the production pipeline cannot do at all.

    python -m rag_pipeline.grounded --models sonnet --limit 2 --dry-run
    python -m rag_pipeline.grounded --models sonnet,grok,gpt5 --tier gold
"""
from __future__ import annotations

import argparse, difflib, json, os, re, sys, unicodedata
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "data", "extractions_grounded")

# ── Prompt ───────────────────────────────────────────────────────────────────

GROUNDED_SYSTEM_PROMPT = """You are a scientific metadata extractor specialising
in computational reproducibility. Every item you emit must quote the passage
text it came from. Return ONLY valid JSON - no markdown, no explanation, no
code blocks."""

GROUNDED_EXTRACTION_PROMPT = """Extract all reproducibility-critical metadata
from the passage below. Return a JSON object with EXACTLY this structure:

{{
  "dependencies":       [{{"name": "string", "version": "string or null", "evidence": "string"}}],
  "random_seeds":       [{{"value": "string", "evidence": "string"}}],
  "hardware":           [{{"slot": "gpu_model|cuda_version|cpu_info|os|ram", "value": "string", "evidence": "string"}}],
  "hyperparameters":    [{{"name": "string", "value": "string", "evidence": "string"}}],
  "datasets":           [{{"name": "string", "version": "string or null", "evidence": "string"}}],
  "methods":            [{{"name": "string", "evidence": "string"}}],
  "evaluation_results": [{{"metric": "string", "value": "string", "split": "string or null", "evidence": "string"}}]
}}

The "evidence" field is mandatory and is the single most important part of your
answer. Rules for it:

- It MUST be copied VERBATIM from the passage, character for character.
- Do NOT paraphrase, summarise, correct spelling, expand abbreviations, or
  reformat numbers inside the quote.
- Keep it short: the shortest span that contains the fact, at most 25 words.
- It MUST contain the value you extracted. If the passage does not state a
  value, do not emit the item at all.
- If you cannot quote the passage for an item, OMIT THAT ITEM. An omitted item
  costs nothing. An item with invented evidence is a serious error.

Other rules:
- Use [] for any field with nothing to report.
- Extract version numbers and metric values exactly as written.
- Only report a random seed when an explicit integer seed is stated.

Passage:
{passage}"""


# ── Free, deterministic verification ─────────────────────────────────────────

def _flat(s: str) -> str:
    """Whitespace- and unicode-insensitive form, for locating a quote.

    Models reflow line breaks and substitute typographic characters even when
    told to copy verbatim, so a raw `in` test under-reports span fidelity and
    would overstate fabrication.
    """
    s = unicodedata.normalize("NFKC", s or "")
    s = (s.replace("‘", "'").replace("’", "'")
           .replace("“", '"').replace("”", '"')
           .replace("–", "-").replace("—", "-")
           .replace(" ", " "))
    return re.sub(r"\s+", " ", s).strip().lower()


def _nospace(s: str) -> str:
    """`_flat` with whitespace removed entirely.

    PDF text extraction routinely drops or inserts word boundaries, so a
    passage can read "Wetrainedthemodelfor1000epochs". A model copying that
    faithfully still fails an exact match if it restores a single space, and
    a model copying correctly from a well-extracted passage fails if the
    extractor dropped one. Whitespace in this corpus is an artifact of the
    PDF layer, not a property of the text, so comparing without it measures
    quoting fidelity rather than extraction noise.
    """
    return re.sub(r"\s+", "", _flat(s))


def span_found_loose(evidence: str, passage: str) -> bool:
    """Whitespace-insensitive span match. Strictly weaker than `span_found`:
    anything the exact check finds, this finds too, so it is only ever
    computed for items the exact check missed."""
    e = _nospace(evidence)
    return bool(e) and e in _nospace(passage)


def span_found(evidence: str, passage: str) -> bool:
    e = _flat(evidence)
    return bool(e) and e in _flat(passage)


def fuzzy_span(evidence: str, passage: str) -> tuple[float, float]:
    """For a quote that is NOT verbatim, how close is the nearest passage text?

    A failed `span_found` has two very different causes and they look identical
    in the output: the model invented the quote, or it paraphrased instead of
    copying. Small open-weight models do the second constantly, so an exact
    check alone cannot support a fabrication claim. These two numbers separate
    them:

    - `longest`: the longest run of evidence characters occurring contiguously
      in the passage, as a fraction of the evidence. A verbatim quote with
      reflowed whitespace scores near 1.0; a paraphrase breaks into short runs
      and scores low.
    - `token_recall`: the fraction of the evidence's content words (3+ chars)
      that appear anywhere in the passage. A paraphrase reuses the source
      vocabulary and scores high; an invention introduces words that are not
      there and scores low.

    Read together: high/high is sloppy quoting, low/low is fabrication, and
    low/high is paraphrase. Only low `token_recall` licenses the word invented.

    Computed only for items that already failed `span_found`, so this changes
    no existing number and costs nothing on the common path.
    """
    e, p = _flat(evidence), _flat(passage)
    if not e or not p:
        return 0.0, 0.0
    sm = difflib.SequenceMatcher(None, e, p, autojunk=False)
    m = sm.find_longest_match(0, len(e), 0, len(p))
    longest = m.size / len(e)
    toks = [t for t in re.findall(r"[a-z0-9]+", e) if len(t) > 2]
    recall = (sum(1 for t in toks if t in p) / len(toks)) if toks else 0.0
    return round(longest, 3), round(recall, 3)


def value_in_span(value, evidence: str) -> bool:
    """Is the extracted value present inside its own quoted evidence?

    Numeric values are compared numerically so that 0.0001 is found inside a
    span that writes 1e-4, which is a formatting difference rather than a
    grounding failure.
    """
    v = _flat(str(value))
    if not v:
        return False
    e = _flat(evidence)
    if v in e:
        return True
    try:
        fv = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return False
    for tok in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", e):
        try:
            if float(tok) == fv:
                return True
        except ValueError:
            continue
    return False


#: field -> the key whose value must appear inside the evidence
_VALUE_KEY = {
    "dependencies": "name", "random_seeds": "value", "hardware": "value",
    "hyperparameters": "value", "datasets": "name", "methods": "name",
    "evaluation_results": "value",
}


def verify(extraction: dict, passage: str) -> list[dict]:
    """One verification record per extracted item. No model, no reference."""
    out = []
    for field, key in _VALUE_KEY.items():
        for item in (extraction.get(field) or []):
            if not isinstance(item, dict):
                out.append({"field": field, "value": item, "evidence": "",
                            "span_found": False, "value_in_span": False,
                            "has_evidence": False})
                continue
            ev = item.get("evidence") or ""
            val = item.get(key)
            found = span_found(ev, passage)
            rec = {
                "field": field, "value": val, "evidence": ev,
                "has_evidence": bool(str(ev).strip()),
                "span_found": found,
                "value_in_span": value_in_span(val, ev),
            }
            if not found and rec["has_evidence"]:
                # Only for misses. First ask whether the miss is nothing but
                # PDF whitespace damage, then how close the nearest text is.
                rec["span_loose"] = span_found_loose(ev, passage)
                lo, tr = fuzzy_span(ev, passage)
                rec["fuzzy_longest"] = lo
                rec["fuzzy_token_recall"] = tr
            out.append(rec)
    return out


def summarise(records: list[dict]) -> dict:
    by = defaultdict(Counter)
    for r in records:
        c = by[r["field"]]
        c["n"] += 1
        c["has_evidence"] += bool(r["has_evidence"])
        c["span_found"] += bool(r["span_found"])
        c["value_in_span"] += bool(r["value_in_span"])
        c["grounded"] += bool(r["span_found"] and r["value_in_span"])
        c["span_any"] += bool(r["span_found"] or r.get("span_loose"))
        # Classify every span miss, so a low span rate can be read rather than
        # merely reported. Thresholds are deliberately blunt: the point is to
        # separate three obviously different populations, not to score them.
        if not r["span_found"] and r.get("has_evidence"):
            if r.get("span_loose"):
                # Matches once whitespace is ignored: a quoting success the
                # exact check cannot see. Counted apart so the strict number
                # stays reported but is not mistaken for infidelity.
                c["miss_whitespace_only"] += 1
                continue
            if "fuzzy_token_recall" not in r:
                # Written before fuzzy scoring existed. Must NOT fall through
                # to "unsupported": that would read as measured fabrication
                # when nothing was measured. Re-score the file to populate it.
                c["miss_unscored"] += 1
                continue
            tr = r.get("fuzzy_token_recall", 0.0)
            lo = r.get("fuzzy_longest", 0.0)
            if lo >= 0.60:
                c["miss_near_verbatim"] += 1
            elif tr >= 0.70:
                c["miss_paraphrase"] += 1
            else:
                c["miss_unsupported"] += 1
    tot = Counter()
    for c in by.values():
        tot.update(c)
    return {"per_field": {k: dict(v) for k, v in by.items()}, "total": dict(tot)}


# ── Runner ───────────────────────────────────────────────────────────────────

def _passages(study_id: str, pdf_url: str, top_k: int = 3) -> list[str]:
    """Retrieved passages for one study, reusing the production retrieval.

    Imported lazily: rag_pipeline.pipeline pulls in the triplestore client at
    module load, and this module must stay importable for its unit tests on a
    machine with no graph store.
    """
    from rag_pipeline.pipeline import RETRIEVAL_QUERIES, download_pdf
    from rag_pipeline.chunker import load_paper
    from rag_pipeline.embedder import EmbeddingStore

    path = download_pdf(pdf_url, study_id)
    chunks = load_paper(path)
    store = EmbeddingStore(study_id)
    if store.is_built():
        # Reuse the index the production sweep used. Rebuilding would be
        # wasteful and, worse, would silently replace the cached index copied
        # from the cluster, so a later comparison against the N3 results could
        # differ for reasons of retrieval rather than of extraction.
        store.load()
    else:
        store.build(chunks)
    seen, out = set(), []
    for q in RETRIEVAL_QUERIES:
        for p in store.retrieve(q, top_k=top_k):
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


def model_slug(model: str | None) -> str:
    """Filesystem-safe slug for a model id. Copied from `rag_pipeline.pipeline`
    rather than imported: that module pulls in the triplestore client and the
    global config for what is a six-line regex, and the grounded pilot needs
    neither. Keeping it local means a cluster job can run this file with only
    the extractor's own dependencies installed. The two must stay in step;
    `tests/test_grounded.py` asserts they agree.
    """
    return re.sub(r"-+", "-",
                  re.sub(r"[^a-z0-9]+", "-", (model or "default").lower())).strip("-")


def out_path(study_id: str, slug: str) -> str:
    return os.path.join(OUT_DIR, f"{study_id}__{slug}.json")


def run_study(study_id: str, pdf_url: str, spec, dry_run: bool = False) -> dict:
    from rag_pipeline.extractor import get_extractor, set_study, _parse_json

    slug = model_slug(spec.model)
    passages = _passages(study_id, pdf_url)
    if dry_run:
        return {"study_id": study_id, "model": spec.key, "slug": slug,
                "n_passages": len(passages), "dry_run": True}

    ex = get_extractor(spec.backend, model=spec.model)
    set_study(study_id)
    records, raw_items, failures = [], [], []
    try:
        for i, passage in enumerate(passages):
            try:
                txt = ex._complete(
                    GROUNDED_SYSTEM_PROMPT,
                    GROUNDED_EXTRACTION_PROMPT.format(passage=passage))
                data = _parse_json(txt)
            except Exception as e:                       # noqa: BLE001
                # Recorded, not just printed. A skipped passage silently
                # shrinks the item count, and on the N3 sweep that class of
                # warning existed only in stdout (paper_notes AC.4).
                failures.append({"passage_index": i,
                                 "error": f"{type(e).__name__}: {str(e)[:200]}"})
                print(f"      passage {i}: {type(e).__name__}: {str(e)[:90]}")
                continue
            for r in verify(data, passage):
                r.update(study_id=study_id, slug=slug, passage_index=i)
                records.append(r)
            raw_items.append({"passage_index": i, "extraction": data})
    finally:
        set_study(None)

    os.makedirs(OUT_DIR, exist_ok=True)
    # `passages` is stored so every check in this file can be recomputed
    # later without re-running the model or re-retrieving. Verification rules
    # change (the whitespace-insensitive match was added after the first four
    # models had already run) and without the source text a re-score means
    # reproducing retrieval exactly, which is a dependency the artifact should
    # not have. Costs roughly 18 KB per file.
    out = {"study_id": study_id, "model": spec.key, "slug": slug,
           "n_passages": len(passages), "n_passages_ok": len(raw_items),
           "failures": failures, "records": records,
           "summary": summarise(records), "raw": raw_items,
           "passages": passages}
    with open(os.path.join(OUT_DIR, f"{study_id}__{slug}.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    return out


def _rows_for(tier: str) -> list[dict]:
    """Study rows for a tier, read straight from the committed CSV.

    Deliberately not routed through run_n3_frontier, which imports the
    pipeline and therefore the triplestore client. This module stays runnable
    and testable without a graph store.
    """
    import csv
    name = "repo_list_gold.csv" if tier == "gold" else "repo_list.csv"
    path = os.getenv("SRAF_REPO_LIST") or os.path.join(ROOT, "validation", name)
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default="sonnet",
                    help="comma-separated registry keys")
    ap.add_argument("--tier", default="gold", choices=["gold", "silver"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true",
                    help="redo studies that already have an output file")
    ap.add_argument("--dry-run", action="store_true",
                    help="retrieve passages and report counts, make no API calls")
    args = ap.parse_args()

    from rag_pipeline.model_registry import resolve, seed_prices
    from rag_pipeline.usage_meter import meter

    specs = resolve(args.models)
    # The meter counts tokens for a model it has no price for, but cannot
    # charge them against the cap, so an unpriced model silently disables the
    # budget guard. run_n3_frontier seeds before any call; this did not, and
    # only stayed capped because prices.json already carried the frontier
    # models from the N3 sweep. The locally served models are not in there at
    # all, so without this they would record as unpriced rather than $0.00.
    seed_prices(meter, specs)
    rows = _rows_for(args.tier)
    if args.limit:
        rows = rows[:args.limit]
    print(f"span-grounded pilot: {len(specs)} model(s) x {len(rows)} studies"
          f"{'  (dry run)' if args.dry_run else ''}\n")

    grand = defaultdict(lambda: Counter())
    for spec in specs:
        print(f"=== {spec.key} ({spec.backend}:{spec.model}) ===")
        for row in rows:
            sid = row.get("study_id") or row.get("id")
            pdf = row.get("paper_url_pdf") or row.get("pdf_url") or ""
            if not pdf:
                print(f"    {sid}: no PDF url, skipped")
                continue
            done = out_path(sid, model_slug(spec.model))
            if not args.force and not args.dry_run and os.path.exists(done):
                print(f"    {sid}: already done, skipping")
                continue
            res = run_study(sid, pdf, spec, dry_run=args.dry_run)
            if args.dry_run:
                print(f"    {sid}: {res['n_passages']} passages")
                continue
            t = res["summary"]["total"]
            n = t.get("n", 0)
            g = t.get("grounded", 0)
            bad = len(res.get("failures") or [])
            print(f"    {sid}: {n:>3} items   span {t.get('span_found',0):>3}"
                  f"   value {t.get('value_in_span',0):>3}"
                  f"   grounded {g:>3} ({(100*g/n if n else 0):.0f}%)"
                  + (f"   [{bad} passage(s) failed]" if bad else ""))
            grand[spec.key]["passages"] += res["n_passages"]
            grand[spec.key]["passage_failures"] += bad
            grand[spec.key].update(t)
        print()

    if not args.dry_run:
        print(f"  {'model':<14}{'items':>7}{'evidence':>10}{'span ok':>9}"
              f"{'value ok':>10}{'grounded':>10}")
        for k, c in grand.items():
            n = c.get("n", 0) or 1
            print(f"  {k:<14}{c.get('n',0):>7}"
                  f"{100*c.get('has_evidence',0)/n:>9.0f}%"
                  f"{100*c.get('span_found',0)/n:>8.0f}%"
                  f"{100*c.get('value_in_span',0)/n:>9.0f}%"
                  f"{100*c.get('grounded',0)/n:>9.0f}%")
        print(f"\n{meter.summary()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
