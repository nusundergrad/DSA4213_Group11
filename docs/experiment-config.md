# Experiment configuration

This configuration is fixed before the 28-condition check on 23 October 2026. The check uses EP_0001's clean report and six single-error copies across baseline, debate, verification and hybrid. Its purpose is to check execution and scoring. One company cannot establish a general effect.

| Setting | Value | Reason |
|---|---|---|
| Model for all roles | `nvidia/nemotron-3-ultra-550b-a55b:free` | Same model throughout avoids comparing model capability alongside architecture. This explicit ID completed the earlier check. The free route reduces execution cost; it is not a claim of superiority. |
| Temperature | `0` | Reduce sampling variation. Hosted execution still need not be identical across repeated requests. |
| Reasoning effort | `none` | Earlier reasoning-enabled runs exhausted their output budgets. This check measures the architectures with reasoning disabled; do not generalize it to other reasoning settings. |
| Maximum output tokens | `6000` per call | The previous completed runs fit within this budget. It leaves room for a full 3–5-claim revision. Keep it identical across roles and conditions; truncation is a failure. |
| Debate rounds | `1` | One Risk Manager review and one Analyst revision is the smallest complete correction exchange. Debate and hybrid get the same number of exchanges. This is a bounded comparison, not a claim that one round is optimal. |
| Initial confidence | Neutral | Keep confidence out of the main architecture comparison. Test other tones separately. |
| Attempts | One per call | Record failed requests and malformed responses instead of silently selecting a successful output. No automatic model fallback. |
| Execution order | Shuffle the 28 conditions with seed `42` | Avoid always running an architecture in the same position. The seed fixes case order only; it is not sent as a model sampling seed. |
| Repetitions | One execution per condition | Suitable for this execution check. Before broader claims, plan additional independent runs rather than selecting the most favorable attempt. |
| Precision | Calculate at full precision, round once to 2 decimals; existing tolerance `0.01` percentage points | Analyst and Risk Manager use the same rule as benchmark generation and verification. A rounded filing quotation is labelled separately from a calculated assertion. |
| Evidence access | Analyst/Risk Manager: masked packet; Trader: current report, verifier output and latest agent message | Preserve the agreed architecture. Private error labels and answer keys never reach agents. |

There are 56 planned model calls: seven baseline, seven verification, 21 debate and 21 hybrid. Verification runs locally. This is not an equal-total-compute comparison: extra model calls are part of the debate/hybrid intervention, so report tokens and latency alongside quality.

If a condition fails solely because of a transient provider/transport error, allow at most one explicit rerun with identical inputs and settings. Preserve the first attempt and report its failure. Do not rerun valid rejections, missed errors, inconvenient results or malformed content to obtain a preferred outcome. Keep first-pass and resumed results distinguishable; select the latest attempt consistently if exporting the resumed set. Authentication/quota failures stop the batch.

## Basis for the choices

[Liang et al., Holistic Evaluation of Language Models (2023)](https://arxiv.org/abs/2211.09110v2) evaluates shared scenarios under standardized conditions, reports multiple metrics and releases prompts and completions. This motivates paired inputs, fixed settings, coverage/efficiency reporting and saved requests/responses here. It does not prescribe this model or these numerical budgets.

[Du et al., Improving Factuality and Reasoning in Language Models through Multiagent Debate (2023)](https://arxiv.org/abs/2305.14325) studies model instances exchanging responses over multiple rounds to improve reasoning and factuality. It motivates testing interaction as an intervention. Our Risk Manager–Analyst exchange is an adaptation, not a replication, and the paper does not establish that one round is best for this benchmark. A three-round comparison can be a separately planned sensitivity test.

[OpenRouter's reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens) explains that reasoning tokens count toward the output budget on most providers. Disabling reasoning and retaining a 6,000-token limit are engineering decisions supported by the earlier execution failures. The [parameter documentation](https://openrouter.ai/docs/api_reference/parameters) describes sampling controls and warns that seeded determinism is not guaranteed for some models. Exact reproducibility also depends on the hosted model/provider, not just request settings.

The model catalog and exact ordered cases are saved with this run. The graph saves configuration/code hashes, input snapshots, requests, responses and available provider usage. A model ID is not an immutable model version. Avoid claiming that this configuration is research-standard or guaranteed to reproduce identical outputs.

## Commands

Run from the repository root after the precision change. Do not overwrite an earlier run folder.

```powershell
python src/evaluation/make_run_list.py --out output/evaluation_check_20261023/cases.json --packets EP_0001 --shuffle-seed 42
python -X utf8 -m src.graph --cases output/evaluation_check_20261023/cases.json --output-root output/evaluation_check_20261023/runs --model nvidia/nemotron-3-ultra-550b-a55b:free --rounds 1 --reasoning-effort none --max-tokens 6000 --max-attempts 1
python src/evaluation/graph_adapter.py output/evaluation_check_20261023/runs --out output/evaluation_check_20261023/evaluation
```

Inspect `pending.json` and `final_report_checks.json`, and read final Trader rationales. Record semantic judgements with reasons before reporting final rates. A corrected injected defect or acceptance of a clean input does not certify the rest of the output. The independent LLM judge and supplementary sensitivity experiments are not part of these 28 conditions.

For the full benchmark, use a new folder and omit `--packets EP_0001` when making the list. With this one-round configuration, 420 conditions require 840 planned calls. If this check exposes a protocol problem, document a new configuration and rerun the affected comparison; do not pool results across versions.

## Full study plan, fixed on 24 October 2026

The 28-condition check above is exploratory and remains separate. Its outputs motivated the scoring clarifications below. Fix this plan before executing the full comparison and confidence subset; retain the Git commit and the runner's saved configuration, code hashes and input snapshots. Changes after execution require a separately labelled analysis or a new run.

| Batch | Tracked case list | Conditions | Planned calls |
|---|---|---:|---:|
| Main: 105 reports, four architectures, neutral | `output/full_cases.json` | 420 | 840 |
| Confidence: 12 reports, baseline/hybrid, three tones | `output/confidence_cases.json` | 72 | 144 |
| Identical neutral repeat of those 12 reports, baseline/hybrid | `output/confidence_neutral_repeat.json` | 24 | 48 |

Use the model, temperature 0, reasoning `none`, 6,000-token budget, one debate round, one attempt and evidence access in the table above for all three batches. Each case list is shuffled with seed 42. One execution per condition gives a bounded comparison on these 15 companies; it does not estimate stability across many repetitions, models or financial domains. The neutral repeat supplies a small reference for ordinary run variation.

The primary comparison reports detection, correction, resolution, accepted unresolved defect rate, FAR, TAR, new-error review coverage and efficiency. ACCEPT/REJECT assesses support for the report; BUY/HOLD/SELL is a separate action. Record both. Report denominators and missing judgements, including unknown material reliance. A lower FAR does not establish safety if many reliance labels are unknown or revisions introduce other errors. See [scoring rules](evaluation.md).

### Confidence subset

`output/confidence_pairs.json` fixes six pairs before this subset is run. Exclude EP_0001, which was used heavily for exploration. Assign the six error types in alphabetical order to the next six packet IDs. Include each selected flawed report and its clean counterpart. This simple rule spreads the subset across six companies without choosing cases for a desired confidence result; it is not a random sample or an independent held-out benchmark.

| Packet | Pair | Flawed report type |
|---|---|---|
| EP_0002 | PAIR_0006 | Arithmetic |
| EP_0003 | PAIR_0053 | Citation misattribution |
| EP_0004 | PAIR_0010 | Direct factual contradiction |
| EP_0005 | PAIR_0058 | Material omission |
| EP_0006 | PAIR_0017 | Reporting period |
| EP_0007 | PAIR_0066 | Unsupported inference |

Only the initial framing sentence varies:

- Underconfident: `I have low confidence in this assessment.`
- Neutral: `I have moderate confidence in this assessment.`
- Overconfident: `I have high confidence in this assessment.`

Evidence and the initial report stay identical within each comparison. Hybrid can subsequently revise the report, so this tests sensitivity to initial framing through the system. Baseline and hybrid give a small comparison of the unprotected and combined architectures. Six flawed cases cannot establish effects for individual error types.

Compare low/high with neutral using matched ACCEPT/REJECT flips; show clean and flawed examples and the direction of any changes. Support-score changes are secondary, uncalibrated observations. Compare them with the identical neutral repeat before attributing variation to framing. No flips is a valid negative finding. Do not strengthen wording or substitute cases after seeing this batch's results. Reviewer disagreement remains a separate supplementary experiment.

### Run and export

These commands execute the fixed lists; they have not been run as part of preparing this plan. Use fresh output folders. The three batches require 1,032 calls before any eligible retries.

```powershell
$model = "nvidia/nemotron-3-ultra-550b-a55b:free"
python -X utf8 -m src.graph --cases output/full_cases.json --output-root output/main_study/runs --model $model --rounds 1 --reasoning-effort none --max-tokens 6000 --max-attempts 1
python -X utf8 -m src.graph --cases output/confidence_cases.json --output-root output/confidence_study/runs --model $model --rounds 1 --reasoning-effort none --max-tokens 6000 --max-attempts 1
python -X utf8 -m src.graph --cases output/confidence_neutral_repeat.json --output-root output/confidence_repeat/runs --model $model --rounds 1 --reasoning-effort none --max-tokens 6000 --max-attempts 1

python src/evaluation/graph_adapter.py output/main_study/runs --out output/main_study/eval
python src/evaluation/graph_adapter.py output/confidence_study/runs --out output/confidence_study/eval --confidence-pairs output/confidence_pairs.json
python src/evaluation/graph_adapter.py output/confidence_repeat/runs --out output/confidence_repeat/eval --confidence-pairs output/confidence_pairs.json
```

Review `pending.json`, `output_review.json`, `final_report_checks.json` and the original outputs. Save the relevant fields and reasons in `adjudications.json`, then rerun each adapter command with `--adjudications <path>`. Explicit `null` overrides an automatic guess; omitted fields retain automatic values. Copy output-review fields into the same per-run adjudication object. Save adjudications outside the generated worksheet path so export does not overwrite them.

```powershell
python src/evaluation/metrics.py --cases output/main_study/eval/cases.jsonl --runs output/main_study/eval/runs.jsonl --scores output/main_study/eval/scored.jsonl --out output/main_study/findings.md
python src/evaluation/metrics.py --cases output/confidence_study/eval/cases.jsonl --runs output/confidence_study/eval/runs.jsonl --scores output/confidence_study/eval/scored.jsonl --neutral-repeat-runs output/confidence_repeat/eval/runs.jsonl --neutral-repeat-scores output/confidence_repeat/eval/scored.jsonl --out output/confidence_study/findings.md
```

Keep the repeat batch separate: it is a planned replication, not a retry. Do not combine it with the first batch using `--keep-latest`. The confidence export must use the frozen pair list; otherwise the legacy 12-pair selection would give the wrong analysis subset.

Apply the same retry rule to every batch: at most one explicit identical rerun for a transient provider/transport failure. Preserve the original and record the reason. Build a retry list containing only eligible failed conditions; do not resume every failed condition indiscriminately. Malformed content, truncation, valid rejections and missed errors are outcomes, not eligible retries. Stop on authentication/quota failures. Report first-pass completion separately and select the latest eligible attempt consistently for resumed analysis, including an unsuccessful retry. The graph preserves attempts but does not enforce this manual eligibility rule.

### Rebuild the lists, before execution only

```powershell
python src/evaluation/make_run_list.py --out output/full_cases.json --no-tone-variants --shuffle-seed 42
python src/evaluation/make_run_list.py --out output/confidence_cases.json --confidence-pairs output/confidence_pairs.json --confidence-only --situations 0 3 --tone-variants --shuffle-seed 42
python src/evaluation/make_run_list.py --out output/confidence_neutral_repeat.json --confidence-pairs output/confidence_pairs.json --confidence-only --situations 0 3 --no-tone-variants --shuffle-seed 42
```

Tests check the frozen lists, matching controls and tones, six distinct companies and error types, and planned call counts. Adding benchmark cases after this freeze requires a new plan version instead of silently expanding these lists.
