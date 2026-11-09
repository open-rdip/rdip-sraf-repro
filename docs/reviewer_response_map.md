# Response to IJCKG 2026 reviewers — mapping to the journal extension

Scores: 1, 1, 1, 0 (three weak accept, one borderline). The editors plan to
invite **the same reviewers**, so this is a checklist the extension is graded
against, not a courtesy document.

## The shape of the criticism

Four reviewers, four independent sets of comments, but they collapse into five
themes — and two of them were raised by more than one reviewer:

| # | Theme | Raised by | Addressed by |
|---|---|---|---|
| **A** | Why a knowledge graph / ontology at all? | **R1, R4** | new §, N4 |
| **B** | LLM extraction quality is an uncontrolled confound | **R1, R2, R4** | **N3** |
| **C** | Implementation opaque; artifact link not findable | **R1, R4** | **N8** |
| **D** | Aggregate FAIR-R does not predict reproduction | **R1, R2** | **N1** |
| **E** | No result-level reproduction | R2 | workshop paper + **N5** |

Theme B is the single most-cited objection — three of four reviewers — and N3
exists precisely to answer it. Theme A is the most *dangerous*, because it
questions whether the central design choice was justified at all, and no
experiment answers it; it needs argument.

---

## A. Why a knowledge graph? (R1, R4)

> R4: "it is not very clear to me what is the benefit of using ontologies and
> knowledge graphs here, compared to anything else … there are a number of
> different ways in which this could have been done with other technologies."
>
> R1: "the need for a semantic framework (KG-based) is not justified adequately"
> and "why executable SHACL shapes? not justified"

**This cannot be answered by adding results.** Two reviewers independently said
the central design choice is unargued, and a bigger table will not change that.

The workshop camera-ready already contains a version of this argument, written
for `rdip:ExecutionRecipe` — queryable alongside environment facts from the same
study, typed ranges rather than bare strings, and SHACL-validatable with
machinery the rubric already uses. That argument generalises and should be
promoted to a full subsection in the journal version.

What makes it concrete rather than assertive is **N4**: the paper-vs-repo diff is
a query across two independently-derived subgraphs of one study. In a JSON
pipeline that comparison is bespoke code; in the graph it is a query, and the
conflict types are shapes. That is a benefit a flat format does not give, and it
is now implemented rather than claimed.

Answer the SHACL question separately and directly: shapes are executable
*and* auditable, a third party can read the rubric as data rather than
reverse-engineering it from code, and a criterion can be added without touching
the engine. Say this once, plainly.

---

## B. Extraction quality is an uncontrolled confound (R1, R2, R4)

> R1: "how one can eliminate that this is caused by the poor performance of the
> LLMs used to extract and structure the required knowledge?"
>
> R2 (W2): "The accuracy of LLM-based extraction of metadata from papers is low,
> which may introduce noise into the reproducibility evaluation."
>
> R4: "I have a problem interpreting the results comparing the performances of
> different LLMs without knowing the prompts used."

Three of four reviewers. **N3 is the answer and is non-negotiable**: re-run
extraction with two or three frontier models, re-score the corpus with the best,
and re-run N1 on those scores. If the conclusions survive a much stronger
extractor, the confound is closed.

Two pieces of evidence already in hand strengthen this before N3 runs:

- The workshop paper's three open-weight models span 8B–24B and two families,
  and entity-level F1 stays flat (0.230, 0.223, 0.273). Size is not the binding
  constraint.
- The N4 diff run showed conflict counts swinging five-fold **between
  extractors on identical repositories** — Llama-8B claims a seed in 52 of 95
  papers where Qwen finds 9. That quantifies the confound rather than conceding
  it, and it is a stronger statement than the reviewers asked for.

R4's specific ask — **publish the prompts** — is free and must be done (see C).

---

## C. Implementation opaque, artifact not findable (R1, R4)

> R4: "I could try to dig them up from the code repository except that I could
> not find the link to it … in a paper about reproducibility, that so little
> details are given about the process … is quite problematic."
>
> R1: "details of the implemented framework are missing. E.g., How is RAG LLM
> extractor implemented? what is the accuracy of this task?" … "details related
> to SHACL shapes used are missing" … "The actual structure of a resulted KG is
> not presented."

**Checked against the submitted source before writing this.** The artifact is
NOT missing. `main.tex` line 388 has a *Data and Software Availability* section
citing the Zenodo record and `github.com/open-rdip/rdip-sraf-repro`, line 158
states that the prompts, shapes and parser are released, and the repository
README carries a table pointing at `rag_pipeline/extractor.py` and
`sre_engine/shacl/*.ttl`.

So R4 did not fail to find a missing link — they missed a buried one. It sits in
an unnumbered `\subsubsection*` after the conclusion. That is a visibility
defect, and it is worth treating as seriously as an absence, because the effect
on the reviewer was identical and it happened in a paper about reproducibility.

Required in the journal version:

1. Repository URL as a **first-page footnote or in the abstract**, not only in a
   closing section. Keep the Data and Software Availability section as well, with
   the DOI'd archived release.
2. A direct pointer at each first mention: when the prompt is discussed, cite the
   file path inline rather than deferring to a statement at the end.
3. The extraction prompts verbatim in an appendix. R4 asked for them by name, and
   an appendix cannot be missed the way a URL can.
4. RAG parameters stated in text: chunk size 400 words / 50 overlap, six
   retrieval queries, top-k 3, temperature 0. One sentence, currently absent.
5. "Deterministic parser" named concretely: which files, which fields, which
   library — R4 quoted the vagueness of the phrase itself.
6. A figure of an actual resulting KG for one study (R1).
7. The SHACL shapes listed, with one shown in full (R1).

N8 covers most of this; items 2–4 need writing rather than work.

---

## D. Aggregate FAIR-R does not predict reproduction (R1, R2)

> R2 (W3): "The aggregate FAIR-R score does not predict reproducibility outcomes
> (ρ = 0.10–0.16, not statistically significant), raising concerns about the
> validity of the scoring design."
>
> R1: "the results … appear to decrease the significance of the proposed
> framework … what has been done to check the main reason for this outcome?"

Both reviewers ask the same question: *why* did it fail. **N1 answers it** —
57.8 of 100 points are invariant across all 96 repositories, nine of fifteen
criteria have zero variance, and a question everyone answers identically cannot
discriminate. The instrument was built for curated data archives and applied to
working code repositories where most of its questions are automatically "no".

That reframes a weakness into the paper's central finding, and it is exactly what
R1 asked for: the main reason for the outcome, investigated.

Also address R1's Table 3 objection here — if RDF plus ML-RC covers every FAIR-R
criterion, what does FAIR-R add? The honest answer after N1 is that coverage is
not the point: an instrument can cover every criterion and still discriminate
nothing, which is what the variance audit shows.

---

## E. No result-level reproduction (R2)

> R2 (W1): "reproducibility assessment is limited to environment reconstruction,
> and result-level reproduction is not performed."

Done since submission: the RDM-KG workshop paper reports the full result-level
funnel (13 recipes extracted, 0 ran to a number, 17 attempted) with a failure
taxonomy. The journal version cites it as prior work and adds **N5**, the
cross-level linkage — do Level-0 metadata and Level-1 build features predict
Level-2 reproduction? That analysis is only possible because both papers exist,
which is worth saying explicitly.

---

## Editorial fixes (R1)

- Paragraph after Fig. 2: format complementary sources as a list.
- "…we walk one artifact and to end" — broken sentence.
- R1 notes "a few language problems" generally; a full pass is warranted.

---

## What this changes about priorities

N3 moves from "important" to **required**: three of four reviewers named the
extraction confound, and the same reviewers are being invited back.

Theme A needs a *written argument*, not an experiment, and nothing currently
scheduled produces it. It should be drafted early rather than left to the writing
phase, because it is the one objection that cannot be answered with data.

The artifact fixes in C are hours of work against the highest-severity comment in
the set. Do them first.
