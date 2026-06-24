# Result-level reproducibility (RQ #20)

Does a repo that *builds* also reproduce the **numbers claimed in its paper**?
This is the strongest reproducibility test: execute each fully-buildable repo and
compare the metric you obtain against the paper's reported value.

Scope: the **26 full-tier repos** (`final_tier == full`). The claimed numbers come
from the (audited) ground truth's `EvaluationResult` entries. Per the advisors,
even a partial result here is valuable — reproducing the headline metric of a
subset is a strong, honest finding.

## Pieces

| file | role |
|---|---|
| `generate_manifest.py` | builds `manifest.yaml`: 26 repos × their claimed numbers + blank `run`/`obtained` fields |
| `manifest.yaml` | the working document you fill while running (run command + obtained values + status) |
| `run_result.sbatch` | clones one repo, builds its venv, runs `run.command`, logs output |
| `compare_results.py` | classifies each repo reproduced / partial / mismatch / run_failed |

## Workflow

1. **Generate the manifest** (already done; re-run if the GT changes):

       python -m result_repro.generate_manifest

2. **Per repo — fill the run plan.** Open `manifest.yaml`, and for each study:
   - read the repo's README to find the command that produces the headline metric;
   - put it in `run.command` (e.g. `python eval.py --config configs/main.yaml`);
   - stage any required dataset, then set `run.data_ready: true`;
   - note `run.gpu` and a rough `run.est_minutes`.
   Repos that can't be run (data gated, needs many GPUs, >day) → set
   `status: skipped` with a reason in `run.notes`.

3. **Run it** (one job at a time, cluster policy):

       sbatch --export=ALL,STUDY=study003 result_repro/run_result.sbatch
       tail -f logs/result-<jobid>.out

4. **Record the obtained number.** Read the metric off the log and fill
   `obtained:` for that study, then set `status` (the comparator will re-derive
   it, but it documents intent):

       obtained:
         - {metric: "S-measure", value: "0.812", split: "test"}

5. **Compare** (repeat as you fill more):

       python -m result_repro.compare_results --tol 0.05

   Reports per-repo reproduced / partial / mismatch and the reproduced-of-ran
   rate. Tolerance is 5% relative or 0.01 absolute by default (`--tol`,
   `--abs-tol`); `94%` and `0.94` are treated as equal, and metric names match
   fuzzily (`acc`↔`accuracy`).

## Reporting

The paper reports: how many of the 26 were runnable, and of those, how many
reproduced the paper's headline number within tolerance — the build→run→result
funnel (resolve % → build % → run % → result-match %). Mismatches and
run-failures are themselves findings (which metadata gaps caused them).
