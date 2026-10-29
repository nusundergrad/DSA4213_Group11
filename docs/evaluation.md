# Evaluation

Start with the [results notebook](../experiments/explore_results.ipynb). See [the workflow](running-experiments.md) for commands and file locations.

## Study

The main study compares baseline, debate, verification and hybrid on the same 15 clean reports and 90 flawed copies. Each company has six injected error types. Initial confidence is neutral; confidence wording and reviewer challenges are supplementary tests.

Analyst and Risk Manager receive the masked evidence packet. Trader receives the current report, verifier result and latest agent message. Private error descriptions and answer keys are used only for evaluation. Saved inputs, settings and attempts identify what each run received.

## Metrics

| Metric | What counts | Denominator |
|---|---|---|
| Detection | The verifier or reviewer identified the injected defect | Completed flawed runs with known detection; baseline is N/A |
| Correction after detection | A detected defect was resolved | Detected cases with known correction; baseline and verification are N/A |
| Resolution | The injected defect is absent from the whole final report | Completed flawed runs with known resolution |
| FAR in the results notebook (`accepted_unresolved`) | Trader ACCEPT while the injected defect remains | Completed flawed runs with a known outcome |
| Original reliance-based FAR (`false_acceptance`) | ACCEPT, unresolved defect, and expressed reliance on its erroneous part | Completed flawed runs with known false acceptance |
| TAR | Trader ACCEPT on a clean input | Eligible completed clean runs |
| New-error rate | A new factual error in the final report or Trader rationale | Completed outputs with a known new-error label |
| Control challenge rate | A first-review challenge on a clean input | Eligible clean runs with a structured review |
| Efficiency | Tokens, reported cost and latency | Report coverage with each measure |

Each rate shows **count / known outcomes**. Failures and unknown labels are reported separately. All four architectures were assigned 90 flawed cases, but a rate's denominator can be smaller. Compare matched cases when coverage differs.

The notebook's main FAR definition was revised after inspecting results. It uses the existing `accepted_unresolved` calculation and retains the proposal's reliance-based measure for comparison. Saved Markdown reports, `metrics.csv` and `false_acceptance` labels retain the original definition; notebook exports use `far_unresolved` filenames.

The original reliance-based measure needs more evidence. For example, accepting a report with an incorrect 14% growth claim does not establish reliance if the Trader only says "growth". Citing a claim ID alone is also insufficient. Explicitly using 14% to justify ACCEPT establishes expressed reliance, but does not establish causal influence on the decision.

The notebook also gives FAR bounds over all 90 assigned flawed cases: count unknowns and failures as non-events for the lower bound, and as events for the upper bound. These are sensitivity bounds, not confidence intervals. Zero known-label FAR does not establish safety.

ACCEPT/REJECT assesses report support; BUY/HOLD/SELL is a separate action. ACCEPT with HOLD still counts as acceptance. TAR does not establish investment correctness or guarantee that a revision stayed error-free.

## Automatic scoring and manual review

Numerical checks use the stated metric, facts, periods and units. Calculated percentage changes use a 0.01-percentage-point tolerance. A faithfully quoted rounded filing percentage is different from a calculated assertion. No checkable assertion means NOT_CHECKABLE, not PASS.

Automatic scoring supplies initial labels. Semantic review checks the whole Risk Manager response, final report and Trader rationale against the packet and private error criterion:

| Label | Question |
|---|---|
| `answer_key_matches_input` | Does the key describe the error actually injected? |
| `risk_manager_detected` | Did the review identify that specific defect anywhere in its response? |
| `defect_resolved` | Is the defect gone from the entire final report, including the rationale? |
| `materially_used_by_trader` | Did the Trader's expressed reasoning use the erroneous part to support ACCEPT? |
| `new_error_present` | Did the final report or Trader add a factual error absent from the input? |

Record a short reason, evidence IDs and relevant exact quotes. Use `null` for ambiguity. A mismatched claim ID does not negate an explicit detection elsewhere in the review. Correcting only a structured assertion is insufficient if the prose retains the error. A persisting injected defect is not counted again as a new error; intermediate-review-only mistakes are outside the new-error metric.

For manual corrections, save a separate `adjudications.json` keyed by run ID, then pass it to `graph_adapter.py --adjudications`. Omitted fields retain automatic labels; explicit `null` overrides them as uncertain. A minimal example:

```json
{
  "RUN_example": {
    "materially_used_by_trader": null,
    "review_note": "The Trader cites growth but does not establish reliance on the wrong percentage."
  }
}
```

New-error corrections also use `new_error_present`, `new_error_explanation` and `new_error_evidence_ids`. Positive labels need evidence; negative labels require checking both the final report and Trader rationale.

## Factual outcome judge

`outcome_judge.py` reviews saved executions after the application runs. It receives the packet and private key, checks the five labels above, and saves reasons, quotes, requests and usage. Python validates responses and calculates metrics. Invalid responses stay unknown; they do not erase valid deterministic observations.

The judge hides architecture names, tone labels, model names, previous scores and support scores. Report wording and review content can still reveal the condition, so blinding is partial. Evaluation calls are separate from architecture cost and latency. `judge.py` instead measures debate interaction quality; it does not replace factual scoring.

The three-round export covers 499 completed outputs. Saved Gemini primary labels receive a source cross-check using the application model, numerical checks and recorded adjudications of disagreements, missing responses and selected error patterns. Every primary positive reliance label is also examined against the erroneous component. Source-valid metadata repairs remove invalid IDs or unsupported quotes without changing model judgements. Required support for positive labels still has to pass validation. Failed requests and original judgements remain preserved locally; reviewed labels and reasons are in the final export.

This is secondary review. The second model shares the application model family, so correlated mistakes remain possible. Independent human validation remains uncompleted, and agreement is not a judge-accuracy estimate. The calibration did not establish sufficient reliability for unattended judging; source review is therefore required. See the [validation instructions](running-experiments.md#how-to-validate-the-judge-labels).

## Supplementary tests and limitations

- **Confidence:** compare low/high wording with neutral on the same reports, alongside an identical neutral repeat. The notebook uses cases completed in all four conditions. Support scores are uncalibrated. See the [fixed subset](experiment-config.md#confidence-subset).
- **Reviewer challenge:** compare disagreement with a neutral follow-up while report and evidence stay fixed. Correctness labels distinguish useful correction from an incorrect reversal; a verdict flip alone cannot. This is separate from architecture debate, where reports can change.
- **Scope:** 15 companies, related manufactured errors, short packets, one application model and three debate rounds. The 90 flawed reports are not 90 independent companies. Paired intervals resample whole packets; individual rate intervals are descriptive. Comparing these results to the earlier one-round study does not isolate round count: turn instructions and message handling also changed.
- **Benchmark notes:** EP_0008's private contradiction key was corrected to match the saved edit; affected outputs were reassessed without rerunning agents. The correction is preserved in `private/annotation_corrections.json`. EP_0006 retains different arithmetic-error magnitudes in prose and its structured assertion.
- **Comparisons:** keep model, prompts, evidence access and budgets fixed. Preserve failures and select retries by the recorded rule. Claims about performance must include coverage, unresolved acceptances and new errors.
