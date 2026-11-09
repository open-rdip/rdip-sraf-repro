# N10 — how to find the twenty badged papers

Work instruction for filling `validation/repo_list_badged.csv`. Budget roughly
half a day. Verified against the ACM and ReScience sources on 1 Oct 2026.

## 1. The criterion that decides everything

You need papers where **an independent party reproduced the results using the
original authors' artifacts.** Not "code exists". Not "someone re-implemented it".

ACM's own definitions make the distinction explicit:

| badge | means | use it? |
|---|---|---|
| **Results Reproduced** | "main results obtained in a subsequent study by a person or team other than the authors, **using, in part, artifacts provided by the author**" | **YES** |
| Results Replicated | independent validation **without** author materials | **no** |
| Artifacts Evaluated — Reusable | artifacts audited as high quality | weak fallback |
| Artifacts Evaluated — Functional | artifacts documented and exercisable | weak fallback |
| Artifacts Available | a URL exists in a permanent repository; **not formally evaluated** | **no** |

Why this matters for your design: SRAF audits *the original authors' repository*.
A replication written from scratch tells you nothing about that repository — it
tells you the paper's method was sound. Those are different claims, and mixing
them would make the contrast group measure something other than artifact quality.

**The same trap exists in the ML Reproducibility Challenge**, and it is the more
likely one to catch you: many MLRC reports re-implement a paper because the
original had no usable code. A `[Re]` verdict on such a report is a reproduction
of the *result*, not evidence about the *artifact*. You must read each report far
enough to see whether they ran the authors' code.

## 2. Where to look

### ReScience C / ML Reproducibility Challenge — the main ML source

<https://rescience.github.io/read/>

The primary discovery interface. Browsable by volume and year, Volumes 1–11
(2015–2026). MLRC cohorts appear as issues within a volume — Volume 9 (2023–24)
Issue 2 is MLRC 2022, with 40+ articles. Each entry links the PDF (via Zenodo),
the replication code on GitHub, the OpenReview thread, and BibTeX.

Verdicts are graded and stated in the title, which makes triage fast:

- `[Re]` — successful replication ← **your candidates**
- `[~Re]` — partial
- `[¬Re]` — unsuccessful ← also interesting, see §5

Earlier cohorts are indexed on Papers with Code:
<https://paperswithcode.com/rc2022>, `/rc2021`, `/rc2020`.

### ACM Digital Library — badged papers

<https://www.acm.org/publications/policies/artifact-review-and-badging-current>

Search the DL and filter by badge. **Expect a matching problem**: ACM badging is
concentrated in systems, programming languages and databases. NeurIPS, ICML and
ICLR do not use ACM badging at all, so this source will not give you ML papers
resembling your corpus. Use it only if ReScience cannot fill twenty, and record
the domain mismatch when you do.

### Last resort

Conference artifact-evaluation committee reports (MLSys, SIGMOD, OSDI) publish
lists of accepted artifacts. Weaker evidence — usually "Functional", rarely
"Reproduced".

## 3. Per-candidate checklist

For each candidate, in order, stopping at the first failure:

1. **Verdict is `[Re]`** (or ACM *Results Reproduced*).
2. **The replicators used the original authors' code.** Open the report and look
   for it explicitly. Phrases like "we used the authors' implementation" or "we
   ran the official repository" qualify; "we re-implemented the method in
   PyTorch" disqualifies. **This is the step that takes the time. Do not skip
   it.**
3. **The original repository still resolves** and is the one the paper points to.
4. **The original paper PDF is retrievable** (arXiv or the venue).
5. **Year and domain are close to something in your corpus.** Record which study
   in `matched_to`.

Record the evidence: `badge_source` (`MLRC` / `ReScience` / `ACM`),
`badge_level` (`Re` / `Results Reproduced`), `badge_url` (the report, not the
paper). An unverifiable badge claim is not a stratum definition.

## 4. What goes in the CSV

Note carefully: `repo_url`, `paper_url_pdf` and `arxiv_id` are the **original
paper's**, not the replication's. The replication is evidence *about* the
original; it is not the subject of the audit. Getting this backwards would audit
twenty replication repos and answer nothing.

The boolean columns (`has_docker`, `has_seed`, …) and `b_score` can be left
blank — the sweeps compute what they need from the clone.

## 5. Two optional additions worth considering

**Take the `[¬Re]` papers too.** ReScience publishes failed replications with the
same rigour. Ten `[Re]` and ten `[¬Re]` would give you a *graded* contrast rather
than badged-versus-general, and would let you ask whether SRAF separates them —
a sharper test than comparing against your own corpus, because both groups went
through the same independent scrutiny. Worth it if you find them easily; not
worth extending the search.

**Record the replication effort** where the report states it (GPU hours, days of
work). It is free to collect while you are reading the report anyway, and it
feeds N7's cost model directly.

## 6. When the rows are in

```bash
SRAF_REPO_LIST=validation/repo_list_badged.csv \
  python3 build_harness/run_repo_facts_corpus.py --all
SRAF_REPO_LIST=validation/repo_list_badged.csv \
  python3 build_harness/run_tier_b_corpus.py --all
```

Then extraction on the cluster, `paper_repo_diff` over the badged ids, and the
comparison table. Predictions are already recorded in
`docs/n10_badged_contrast.md` — read them before you look at the results, not
after.
