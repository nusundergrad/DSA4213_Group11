# Evaluation workflow

## Read the completed results

1. Open [explore_results.ipynb](../experiments/explore_results.ipynb) and click **Run All**.
2. Read the tables and charts. Each rate shows its numerator and denominator. The example cell lets you inspect an individual decision.
3. Use `output/final_evaluation_3rounds_20261027/findings.md` for written findings and its `figures/` folder for presentation charts.

This uses saved results and makes no model calls. It needs the project requirements, pandas, matplotlib and a Python notebook kernel.

The notebook's main FAR is acceptance with the injected error unresolved. This definition was revised after inspecting results. Saved Markdown reports and `metrics.csv` retain the original reliance-based FAR; the notebook compares both and saves the revised results in `far_unresolved` files.

The three-round study has **411/420 completed main runs, 65/72 confidence runs and 23/24 neutral repeats**. The 17 failed conditions and uncertain labels remain visible. Debate and hybrid each use three Risk Manager–Analyst rounds.

## Final evaluation

The current results are in **`output/final_evaluation_3rounds_20261027/`**. Within each study folder:

| File | Contains |
|---|---|
| `cases.jsonl` | Private error descriptions and expected corrections |
| `runs.jsonl` | Saved agent outputs |
| `scored.jsonl` | Evaluation labels, reasons and supporting quotes |
| `findings.md` | Metrics, coverage and comparisons |

### Browse individual agent runs

Open `main_study_3rounds/runs/` inside the final-results folder. Files are grouped like the earlier study:

```text
runs/
  EP_0001/
    situation_0/
      clean/<timestamp>.json
      error_03_arithmetic/<timestamp>.json
    situation_1/
    situation_2/
    situation_3/
```

Situations 0–3 are baseline, debate, verification and hybrid. Each case contains the single attempt selected for the final evaluation, including failed conditions. Confidence study folders add the tone before the filename, for example `clean/underconfident/<timestamp>.json`.

These are unchanged copies of the full original runs. Read `final_reports` for the initial Analyst report and revisions, `risk_manager_turns` for the reviews, `verifier_reports` for every verifier pass, and `trader_verdict` for the final decision. Failed attempts contain whatever was saved before failure.

The root `run_index.csv` maps each readable file to its run ID, original path and recovery status. The original `output/main_study_3rounds/runs/chunk_*` folders remain as execution history; use the final-results view for browsing.

The root `findings.md` summarises all three studies. `uncertain.json` lists ambiguous judgements, `decisions.json` records source-review decisions, and `execution_coverage.csv` shows first-pass and recovery counts.

Other dated output folders hold earlier exports and review notes. You do not need to work through them to read the final results.

### Rebuild only if needed

From the repository root:

```powershell
python experiments/finalize_three_rounds.py
```

Then run the results notebook. This reapplies saved review decisions and rebuilds metrics. It costs nothing and does not rerun agents or generate new judgements.

The individual run copies are already included in the final-results folder. To recreate that view from the original local attempts, add `--organize-runs` to the command. The ordinary rebuild uses the saved JSONL inputs and leaves the readable run copies in place.

### Share with teammates

The final results and inputs for rebuilding them are ordinary files, allowed by `.gitignore`. Include them when committing to share the [findings](../output/final_evaluation_3rounds_20261027/findings.md), notebook and rebuild command. Temporary working files remain ignored. Nothing is uploaded by the rebuild command.

## How the evaluation works

**Saved agent runs -> factual labels -> review corrections -> metrics and charts.**

The primary judge checks each output against the evidence and private error description. A second model pass, numerical checks and recorded source adjudications check those labels. Python calculates rates from the saved decisions. This is not independent human validation; model agreement can still miss errors.

Read [evaluation.md](evaluation.md) for metric definitions and review rules. The original FAR also needs expressed reliance on the error; the notebook's main FAR uses acceptance and resolution. Unknown labels are excluded from rates and reported alongside them.

## How to validate the judge labels

For the current study, inspect reasons and source quotes in `scored.jsonl`, then check the corresponding packet and agent outputs using the example cell in the results notebook. `review_summary.json` describes coverage and limitations. The older [review_sample.ipynb](../experiments/review_sample.ipynb) refers to the previous one-round study.

For an independent human check, read the packet and outputs before looking at the saved labels, record the five labels defined in [evaluation.md](evaluation.md), then compare. Record any earlier exposure to the labels. The older `check_judge_labels.ipynb` illustrates this process but points to the previous sample. Independent human validation has not been completed.

## Run a new experiment

Follow the [three-round configuration and commands](experiment-config.md#three-round-runs-25-october-2026), using new output folders. Run the agents, export their records, review the labels, then calculate metrics. The current finalizer only rebuilds the completed three-round study. The previous one-round results remain in `output/final_evaluation_20261024/`; their separate rebuild script is `experiments/finalize_evaluation.py`.

The main study compares four architectures with neutral wording. Confidence wording and reviewer disagreement are separate supplementary tests. Keep settings fixed within a comparison and preserve failed attempts.
