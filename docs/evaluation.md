# Evaluation

See [running the experiments](running-experiments.md) for the commands.

The main comparison uses neutral framing across baseline, debate, verification and hybrid.
Confidence wording and reviewer challenges are supplementary experiments. The justification does not establish a reliable confidence effect.

## Inputs and separation

The current benchmark has 15 packets, 15 clean reports and 90 flawed reports.
`benchmark_cases.py` reads the private pair records after execution. Each clean report is one control, shared by its six flawed copies.
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
| Accepted unresolved defect rate | Trader ACCEPT with an unresolved injected defect, without requiring material reliance. |
| FAR | Trader accepted, the defect remained unresolved, and the Trader materially relied on it. |
| TAR | Trader accepted a clean input. This does not establish that later revisions stayed correct, or measure trading profitability. |
| Control challenge rate | First-review challenges on clean reports. Review them before calling them false challenges. |
| New-error rate | At least one new error in the final Analyst report or Trader rationale, among completed outputs with a known review label. |
| Efficiency | Reported tokens, cost and latency. Unknown cost is not zero. |

Each metric uses its own known-label denominator. Failed executions and unknown labels never count as successes.
For accepted unresolved defect rate, REJECT or a resolved defect counts as false; ACCEPT with unknown resolution stays unknown. FAR adds a material-reliance judgement, so its denominator may be smaller. Report both rather than interpreting unknown reliance as successful containment.
ACCEPT/REJECT is a report-support assessment. BUY/HOLD/SELL is a separate action: accepting a report can still lead to HOLD. Action counts do not measure investment correctness or profitability.
A pending detection judgement does not hide a known REJECT from FAR. Exported failed runs have pending score records to keep joins and coverage valid.
The report displays coverage; inspect missing conditions in `run_plan.json` as well. Conditions never started after a quota stop are not completed observations.

## Automatic scoring and manual review

- Structured numerical failures can identify wrong numbers, arithmetic or reporting periods. No assertion means NOT_CHECKABLE, not PASS. Numerical PASS does not establish that prose is supported.
- A final claim exactly matching the clean text, citations and assertion is resolved. An unchanged flawed claim is unresolved.
- A matching `check_spec` alone is not a correction. Other edits, missing/renumbered claims and semantic changes need review.
- Trader REJECT is not a false acceptance. Its self-reported claim reliance is a useful trace, not proof; validate questionable cases.
- Matching reviewer type/value is a suggestion. The default keeps semantic detection pending. Human adjudication checks the specific defect criterion, even if the reviewer used a different category name.
- A challenge can use `target_claim_id: null` for a rationale error or omitted claim. Match it to the private criterion through review; a null target alone is not detection. Claim-only reliance fields cannot establish whether a rationale error was materially used, so that judgement stays pending even with `--unrelied-is-immaterial`.

The adapter writes `pending.json`. Read each run and the private criteria, then supply booleans or explicit `null` in a separate adjudication file keyed by run ID. An omitted field keeps its automatic value; `null` deliberately marks it uncertain, even if the automatic claim-ID rule suggested material reliance. Store reasons in `review_note`. Do not fill unknowns merely to complete a results table.

`output_review.json` lists every completed run, including clean controls. Copy its fields into the same adjudication file after checking the final Analyst report and Trader rationale against the initial report and full packet:

```json
{
  "RUN_example": {
    "materially_used_by_trader": null,
    "review_note": "The claim is cited but the rationale does not establish use of its erroneous number.",
    "new_error_present": true,
    "new_error_explanation": "The revision corrected C1 but added a wrong fiscal year in C2; E02 gives the correct period.",
    "new_error_evidence_ids": ["EP_0001_E02"]
  }
}
```

New errors must be absent from the input and present in the final report or Trader rationale. Do not count a persisting injected defect again. For unsupported additions, cite the relevant evidence and explain what it supports and what is missing. Errors only in an intermediate message are outside this final-output metric. `true` requires an explanation and evidence IDs; `false` requires an explanation of the completed check. Unreviewed or ambiguous outputs stay `null`. Primary defect scoring can be complete while this separate review remains pending. Report reviewed/completed coverage; an empty review set is not a zero error rate.

## Supplementary tests

Initial confidence: the [frozen plan](experiment-config.md#full-study-plan-fixed-on-24-october-2026) has six clean/flawed pairs across six companies, baseline/hybrid, three tones and a separate neutral-repeat batch. Pass `--confidence-pairs output/confidence_pairs.json` when generating and exporting this subset. Without it, the legacy 12-pair selection remains available for earlier experiments. Report verdict flips and neutral-repeat variation; support scores are uncalibrated secondary measures. The metrics CLI accepts the repeat batch with `--neutral-repeat-runs` and `--neutral-repeat-scores` and rejects reused records or changed inputs/settings.

Reviewer challenge: `challenge_experiment.py` shares one initial review between neutral-check and disagreement branches. Both keep report and evidence fixed, then request a final assessment. A flip alone is neither a useful correction nor an incorrect reversal. Those metrics require adjudicated initial/final correctness; unresolved judgements stay pending.
This is a scripted reviewer follow-up test, separate from the architecture debate, where reports can change.

`judge.py` optionally measures debate interaction quality with an independent model. Its scores do not replace the private answer key or human adjudication.

## Interpretation

Variants from one company share evidence, so 90 flawed reports are not 90 independent companies. Per-rate Wilson intervals are descriptive. Paired difference intervals resample whole evidence packets to retain the shared-company structure. No bootstrap interval is reported for a single packet; even with a few packets, intervals do not establish generality. The raw McNemar helper remains available but its case-independence assumption does not hold for grouped variants.
Keep model, reasoning budget, debate rounds, evidence access and prompts fixed within a comparison. The metrics reject mixed model/configuration settings. Preserve failed and earlier attempts; select reruns by a fixed rule, never by the desired result.
The benchmark can support an initial comparison across six error types. A small application check validates the pipeline, not the hypothesis or an error rate for finance generally.
