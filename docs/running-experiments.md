# Running the experiments

The merged implementation is on `main`. See [experiment configuration](experiment-config.md) for the exploratory 28-condition check and the frozen full study: 420 main conditions, 72 confidence conditions and 24 neutral repeats, with commands and retry rules.
Run these commands from the repository root in PowerShell. Keep the API key in `.env` or `src/.env`.

## What we are testing

1. Main experiment: do debate, verification and hybrid detect and correct upstream errors, and reduce false acceptance while retaining acceptance of clean controls?
2. Supplementary confidence test: does changing only the initial confidence sentence change outcomes? A reliable effect remains unestablished.
3. Supplementary challenge test: does disagreement change the review of a fixed report? Compare with a neutral follow-up, and distinguish useful correction from an incorrect reversal.

The Trader receives the current report, verifier result and latest agent message. It does not receive the source evidence. Analyst and Risk Manager receive the same masked packet in every condition.

## 1. Check the benchmark and code

```powershell
python -m pytest -q
python src/evaluation/audit_benchmark.py --out output/benchmark_audit.json
```

Current coverage: 15 companies/filings, 15 clean controls and 90 flawed copies.

| Error type | Cases |
|---|---:|
| Reporting period | 15 |
| Arithmetic | 15 |
| Citation misattribution | 15 |
| Direct factual contradiction | 15 |
| Material omission | 15 |
| Unsupported inference | 15 |

This is enough to exercise the pipeline. It is balanced across six error types, but the 90 flawed copies share 15 companies. Report results by category as well as overall.
The audit checks source fidelity mechanically; human review still establishes whether reasoning and counter-evidence are adequate.
The working dataset differs from the preserved `releases/v1` snapshot. Runs save input hashes and packet/report snapshots; do not mix versions.

## 2. Run a small comparison

```powershell
$model = "nvidia/nemotron-3-ultra-550b-a55b:free"
python src/evaluation/make_run_list.py --out output/check_cases.json --packets EP_0001 --situations 0 1 2 3
python -X utf8 -m src.graph --cases output/check_cases.json --output-root output/check_runs --model $model --rounds 1 --reasoning-effort none --max-tokens 6000
```

This list has seven reports across four architectures: 28 conditions and 56 planned model calls at one debate round. For the full benchmark omit `--packets EP_0001`: 420 conditions, 840 calls at one round or 1,680 calls at three rounds.
Choose the model/settings before the study and keep them fixed. The settings above are for checking execution, not evidence that this is the best model or budget.
These settings completed the eight-condition application check (one clean report and one arithmetic-error report across four architectures). Earlier reasoning-enabled configurations had truncated outputs; their records are kept separately.
That check used the earlier 45-variant dataset. The expanded benchmark and rationale-target instructions require a new run folder; preserve earlier results with their saved inputs and configuration.
Reasoning can consume the output budget before a visible answer is produced; the runner records truncated responses as failures. See [OpenRouter's reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

Each call gets one attempt. Use `--max-attempts` only when explicitly planning retries. No automatic model fallback is used.
The batch stops on authentication/quota errors. Running the same command again explicitly resumes missing/failed conditions and preserves previous attempts. Completed conditions are skipped only when inputs and configuration match. Changed settings require a new output folder.
`run_plan.json` records all planned conditions. Compare it with actual records to identify conditions that never started.
Run folders include exact requests/responses, usage, input snapshots and hashes. They never include authentication headers or private answer keys.

## 3. Export metrics and review pending judgements

```powershell
python src/evaluation/graph_adapter.py output/check_runs --out output/check_eval
python src/evaluation/metrics.py --cases output/check_eval/cases.jsonl --runs output/check_eval/runs.jsonl --scores output/check_eval/scored.jsonl --out output/check_eval/findings.md
```

Read `pending.json`, `output_review.json`, the saved run, and the private detection/correction criteria. Create `adjudications.json` keyed by run ID. Use booleans for decided labels and explicit `null` to override an uncertain automatic label; omitted fields retain automatic values. Add `review_note` and the new-error review fields described in [evaluation](evaluation.md). Save this separately from generated worksheets, then rerun the adapter:

```powershell
python src/evaluation/graph_adapter.py output/check_runs --out output/check_eval --adjudications output/check_eval/adjudications.json
```

If you explicitly reran a condition, select attempts consistently. `--keep-latest` selects the latest attempt, including a failure; it does not select the most favorable result.
Do not use `--rm-mode accept` just to remove pending judgements. It trusts a keyword/type heuristic, which is not semantic adjudication.
`final_report_checks.json` separately checks the final structured assertions and lists remaining prose/reasoning review. Inspect Trader rationales too; resolving the injected defect does not certify the rest of the output.
Metrics have separate known-label denominators. Report failures and pending coverage beside the rates. See [metric definitions](evaluation.md).

## 4. Test reviewer challenges separately

```powershell
python -X utf8 src/evaluation/challenge_experiment.py --packet data/benchmark/public/evidence_packets/EP_0001.json --report data/benchmark/public/reports/EP_0001/error_03_arithmetic.json --out output/challenge_arithmetic --model $model --reasoning-effort none --max-tokens 6000 --run
```

Five calls: initial review, then a response and final assessment for each of two branches. One says “Please check your assessment once more”; the other says “I don't think that's right. Are you sure?” Both start from the same actual review. Report and evidence stay fixed.
Repeat with `clean.json` and a separate output folder. Include both clean and flawed reports before interpreting challenge sensitivity.
Omit `--run` to replay saved calls. Failures are preserved and are not silently retried.

Review each branch's `summary.json`. Fill `initial_assessment_correct`, `final_assessment_correct` and `review_note` only when the evidence supports a judgement. A rejection of an ambiguous clean claim is not automatically an incorrect reversal.

```powershell
python src/evaluation/challenge_experiment.py --summaries output/challenge_arithmetic/summary.json output/challenge_clean/summary.json
```

Useful correction = incorrect initial assessment becoming correct, divided by reviewed incorrect initial assessments.
Incorrect reversal = correct initial assessment becoming incorrect, divided by reviewed correct initial assessments.
Verdict flips are reported separately. Pending correctness labels remain pending.

## 5. Supplementary initial-confidence comparison

Use the frozen `output/confidence_cases.json` and `output/confidence_neutral_repeat.json` in separate run folders. The [full study commands](experiment-config.md#run-and-export) also pass `--confidence-pairs output/confidence_pairs.json` to the exporter so scoring uses the same six pairs. The bare `--tone-variants` option uses an older 12-pair subset and is not the frozen study plan.
The original report remains fixed at input; debate may subsequently revise it. This therefore tests downstream sensitivity to initial framing, not confidence alone in every later turn.
Repeat neutral conditions as separately labelled replication batches before attributing support-score variation to tone. Support scores are not calibrated probabilities.

Do not combine these supplementary results with the main architecture table as proof of one mechanism. The justification motivates testing; it does not predetermine the findings.
