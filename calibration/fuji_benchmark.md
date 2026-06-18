# F-UJI benchmark procedure

Companion to `run_calibration.py`. This is check (2) of the calibration plan
(docs/fair_r_scoring_rubric.md §5): establish **comparability with the reference
standard tool** by scoring the same objects with F-UJI and comparing
per-dimension results.

F-UJI assesses **datasets identified by a resolvable PID** (DOI/Handle), not
code repositories. So the benchmark covers the **F / A / I / R dimensions** of
the FAIR-R score on the subset of corpus artifacts that expose a dataset PID
(e.g. a Zenodo/Figshare deposit, or a DataCite-registered dataset). The novel
**Reproducible** dimension has no F-UJI analogue and is excluded from this
comparison — that gap is exactly why our rubric extends FAIR with FAIR4RS + the
ML Reproducibility Checklist.

## 1. Stand up F-UJI

F-UJI ships as a server + client (Apache-2.0, FAIRsFAIR / Horizon 2020).

    # option A — Docker
    docker run -p 1071:1071 ghcr.io/pangaea-data-publisher/fuji:latest
    # API docs then at  http://localhost:1071/fuji/api/v1/ui/

    # option B — from source
    git clone https://github.com/pangaea-data-publisher/fuji
    cd fuji && pip install -e . && python -m fuji_server -c fuji_server/config/server.ini

A public demo endpoint also exists (https://www.f-uji.net) but rate-limits;
prefer a local instance for a batch.

## 2. Assemble the comparison subset

From the corpus, take every study whose KG carries a dataset PID:

    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX rdip: <https://w3id.org/rdip/>
    SELECT ?study ?pid WHERE {
      GRAPH ?study {
        ?d a dcat:Dataset ; rdip:identifier ?pid .
        FILTER(STRSTARTS(STR(?pid), "https://doi.org/") ||
               STRSTARTS(STR(?pid), "https://hdl.handle.net/"))
      }
    }

Record `(study_id, pid)` pairs. (If few corpus repos expose a dataset DOI,
supplement with the `external` Zenodo-deposited reference artifacts.)

## 3. Score each PID with F-UJI

    curl -X POST http://localhost:1071/fuji/api/v1/evaluate \
         -H 'Content-Type: application/json' \
         -u marvel:wonderwoman \
         -d '{"object_identifier":"<PID>","test_debug":true,"use_datacite":true}'

The response reports a percent per FAIR principle and an overall maturity level.
Map F-UJI principle groups to our dimensions:

| FAIR-R dimension | F-UJI principle group | F-UJI metrics (examples) |
|---|---|---|
| Findable      | F | FsF-F1-01D/02D, F2-01M, F3-01M, F4-01M |
| Accessible    | A | FsF-A1-01M, A1-02M/03D |
| Interoperable | I | FsF-I1-01M/02M, I3-01M |
| Reusable      | R | FsF-R1-01MD, R1.1-01M, R1.2-01M, R1.3-01M/02D |
| Reproducible  | — | (no F-UJI equivalent — excluded) |

## 4. Compare

For each study, normalise both tools to **percent per dimension** (our scorer
already exposes `dimension_scores[d]["percent"]`; F-UJI reports percent per
principle). Then report, across the subset:

* per-dimension **mean absolute difference** (|FAIR-R% − F-UJI%|),
* **Spearman rho** between the two tools' per-dimension percents (agreement on
  ranking of artifacts),
* a short table of the largest disagreements with the likely cause (e.g. F-UJI
  rewards a registered DataCite landing page our lifter did not capture, or our
  rubric credits an SPDX licence string F-UJI could not resolve).

Close agreement on F/A/I/R substantiates that the standard-overlapping part of
the rubric behaves like the community tool; systematic gaps are documented as
known scope differences (repo-level vs dataset-level evidence).

## 5. Report in the paper

One paragraph + one table in the validation section: "On the *n* artifacts with
a resolvable dataset PID, FAIR-R's F/A/I/R dimensions agree with F-UJI to within
*x* percentage points (Spearman rho = *r*); the Reproducible dimension has no
F-UJI counterpart and is validated separately against reproduction outcomes
(RQ4)."

## Reference

Devaraju, A. & Huber, R. (2022). *An automated solution for measuring the
progress toward FAIR research data (F-UJI).* Patterns 3(11). Methods:
https://www.f-uji.net/index.php?action=methods · Code:
https://github.com/pangaea-data-publisher/fuji
