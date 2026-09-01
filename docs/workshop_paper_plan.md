# IJCKG Workshop Paper — Plan

**Working title:** *Can a Paper Reproduce Its Own Numbers? An Engine-Driven Study of
Result-Level Reproduction and a Taxonomy of Failure*

**Deadline:** September 5, 2026 (~13 days from Aug 23)
**Venue:** IJCKG 2026 co-located workshop (assume CEUR/LNCS, ~6–8 pages — confirm)
**Relationship to main paper:** companion, not overlap. Main = static FAIR-R
prediction; this = dynamic execution + failure taxonomy. Cites the main paper for
the RDIP/FAIR-R apparatus; does not re-derive it.

---

## The one-sentence contribution
An engine that, for any paper, extracts *how to reproduce it* as metadata, runs it,
and compares to the claimed number — plus the first automatically-derived,
result-level **taxonomy of why computational results fail to reproduce**, grounded
in a real corpus and linked back to FAIR-R metadata.

## Why it complements the main paper (both stay strong)
- Main paper *predicts* reproducibility from metadata (RQ1). This paper *tests* the
  prediction by actually running the code — validating the main paper's premise.
- Each failure category maps to a missing metadata element the main rubric scores,
  so the taxonomy is the "so what" of the FAIR-R score, not a duplicate of it.
- No shared results tables: main owns scoring/correlation; workshop owns the
  reproduction funnel + taxonomy.

## Section outline
1. **Introduction** — reproducibility crisis in ML; the gap between *building* code
   and *reproducing the reported number*; contributions.
2. **Related work** — reproducibility studies (ML-RC, ReScience), FAIR-for-software,
   LLM code agents. Position: prior surveys list failures *manually*; ours is
   *automatic, result-level, and ontology-linked*.
3. **Engine-driven recipe extraction** — the key idea: the run command is *extracted
   as metadata* (rdip:ExecutionRecipe), not hand-written, so it generalizes to new
   papers. Two-phase design (recipe extraction / execution) + streaming cleanup.
4. **Study design** — corpus (96 papers with code → 26 build), the funnel metric,
   tolerance for "reproduced," and the **positive controls** (papers known to
   reproduce) that calibrate the engine. State each study's evaluation criterion and
   why it is easy/hard to reproduce (professor's ask).
5. **Results** — the funnel (96 → 26 → 17 → recipe → ran → reproduced) with positive
   controls reproducing, and the failure **taxonomy** (kept at current granularity —
   professor: deeper is hard to maintain).
6. **Discussion: what to fix and how** (professor's ask) — for each failure family,
   classify the remedy: (a) needs further research, (b) author documentation fix
   (name the exact missing metadata), or (c) a stronger extraction agent / LLM.
   Propose specific measures per category.
7. **Threats to validity** — imperfect claim extraction (F1≈0.27, so "reproduced
   against extracted claims"), our-environment blockers (unzip/pip — now controlled),
   small runnable-N, GT incompleteness.
8. **Conclusion + future work** — semantic diff (RQ2), LLM-as-judge for the compare
   step, broader corpus.

## Must-do before writing (blocking the results section)
- [ ] Fix the outstanding code bug.
- [ ] Add 3–5 **positive-control** papers known to reproduce; confirm the engine
      reproduces at least some. (Load-bearing — the whole result depends on it.)
- [ ] Re-run study020/021 with the new unzip shim so their blocker is the artifact's,
      not ours.
- [ ] Produce the final corpus funnel + taxonomy counts from summarize.py.
- [ ] Per-study evaluation-criterion + easy/hard-to-reproduce note.

## Later (not this paper)
- LLM-as-judge for the compare step (professor pointed at a survey) — future work.
- Semantic diff (RQ2) — the journal extension, not the workshop.
- Present to the cybersecurity colleague (ex-Arcos) for comments.

## Timeline to Sep 5
- **Aug 23–26:** fix bug, pick + run positive controls, re-run 020/021, lock numbers.
- **Aug 27–31:** draft sections 3–6 (the engine, design, results, discussion).
- **Sep 1–3:** intro/related/threats/conclusion; figures (reuse funnel + taxonomy).
- **Sep 4:** full read-through, tighten, references, page limit.
- **Sep 5:** submit.
