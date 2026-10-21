# Evaluation

See [running the experiments](running-experiments.md) for the commands.

The main comparison uses neutral framing across baseline, debate, verification and hybrid.
Confidence wording and reviewer challenges are supplementary experiments. The justification does not establish a reliable confidence effect.

## Inputs and separation

The current benchmark has 15 packets, 15 clean reports and 45 flawed reports.
`benchmark_cases.py` reads the private pair records after execution. Each clean report is one control, shared by its three flawed copies.
Agents receive masked public content, never filenames, error labels or expected answers.
Use `audit_benchmark.py` before a batch. It checks source spans, hashes, masking, numbers and exact recorded pair edits; it does not replace semantic review.

Agent visibility follows `main`: Analyst and Risk Manager receive the packet. Trader receives the current report, current verifier result and latest agent message, without the source packet or full discussion.
Structured challenge and reliance fields are evaluation instrumentation. They may affect model responses and should be stated in the methodology.
Actual Analyst revisions are preserved, including new errors. The runner does not restore unchallenged claims.

## Metrics

| Metric | Meaning |
|---|---|
| Detection | A verifier or reviewer identified the frozen injected defect. Merely mentioning the target claim is insufficient. |
| Correction after detection | The injected defect was resolved among cases where it was detected. Baseline and verification-only correction are N/A. |
| Resolution | The injected defect is absent from the final claim, regardless of detection. This does not certify the whole report. |
| FAR | Trader accepted, the defect remained unresolved, and the Trader materially relied on it. |
| TAR | Trader accepted a clean input. This does not establish that later revisions stayed correct, or measure trading profitability. |
| Control challenge rate | First-review challenges on clean reports. Review them before calling them false challenges. |
| Efficiency | Reported tokens, cost and latency. Unknown cost is not zero. |

Each metric uses its own known-label denominator. Failed executions and unknown labels never count as successes.
A pending detection judgement does not hide a known REJECT from FAR. Exported failed runs have pending score records to keep joins and coverage valid.
The report displays coverage; inspect missing conditions in `run_plan.json` as well. Conditions never started after a quota stop are not completed observations.

## Automatic scoring and manual review

- Structured numerical failures can identify wrong numbers, arithmetic or reporting periods. No assertion means NOT_CHECKABLE, not PASS. Numerical PASS does not establish that prose is supported.
- A final claim exactly matching the clean text, citations and assertion is resolved. An unchanged flawed claim is unresolved.
- A matching `check_spec` alone is not a correction. Other edits, missing/renumbered claims and semantic changes need review.
- Trader REJECT is not a false acceptance. Its self-reported claim reliance is a useful trace, not proof; validate questionable cases.
- Matching reviewer type/value is a suggestion. The default keeps semantic detection pending. Human adjudication checks the specific defect criterion, even if the reviewer used a different category name.

The adapter writes `pending.json`. Read each run and the private criteria, then supply booleans in a separate adjudication file keyed by run ID. Preserve notes explaining judgement calls. Do not fill unknowns merely to complete a results table.
Check every final report and rationale for newly introduced errors separately; resolving the injected defect does not prove the final report is clean.

## Supplementary tests

Initial confidence: `make_run_list.py --tone-variants` adds fixed low/high statements to a predefined subset. Report verdict flips and neutral-repeat variation; support scores are uncalibrated secondary measures.

Reviewer challenge: `challenge_experiment.py` shares one initial review between neutral-check and disagreement branches. Both keep report and evidence fixed, then request a final assessment. A flip alone is neither a useful correction nor an incorrect reversal. Those metrics require adjudicated initial/final correctness; unresolved judgements stay pending.
This is a scripted reviewer follow-up test, separate from the architecture debate, where reports can change.

`judge.py` optionally measures debate interaction quality with an independent model. Its scores do not replace the private answer key or human adjudication.

## Interpretation

Variants from one company share evidence, so 45 flawed reports are not 45 independent companies. Per-rate Wilson intervals are descriptive. Paired difference intervals resample whole evidence packets to retain the shared-company structure. With very few packets, those intervals do not establish generality. The raw McNemar helper remains available but its case-independence assumption does not hold for grouped variants.
Keep model, reasoning budget, debate rounds, evidence access and prompts fixed within a comparison. The metrics reject mixed model/configuration settings. Preserve failed and earlier attempts; select reruns by a fixed rule, never by the desired result.
The benchmark can support an initial comparison across seven error types. A small application check validates the pipeline, not the hypothesis or an error rate for finance generally.
