# Evaluation workflow

## Read the completed results

1. Open [explore_results.ipynb](../experiments/explore_results.ipynb) and click **Run All**.
2. Read the tables and charts. Each rate shows its numerator and denominator. The example cell lets you inspect an individual decision.
3. Use `output/final_evaluation_20261024/findings.md` for written findings and `figures/` for presentation charts.

This uses saved results and makes no model calls. It needs the project requirements, pandas, matplotlib and a Python notebook kernel.

The study has 414/420 completed main runs, 70/72 confidence runs and 22/24 neutral repeats. Failed runs and uncertain labels remain visible.

## Final evaluation

The current results are in **`output/final_evaluation_20261024/`**. Within each study folder:

| File | Contains |
|---|---|
| `cases.jsonl` | Private error descriptions and expected corrections |
| `runs.jsonl` | Saved agent outputs |
| `scored.jsonl` | Evaluation labels, reasons and supporting quotes |
| `findings.md` | Metrics, coverage and comparisons |

The root `findings.md` summarises all three studies. `uncertain.json` lists ambiguous judgements, and `label_changes.json` records review corrections.

Other dated output folders hold earlier exports and review notes. You do not need to work through them to read the final results.

### Rebuild only if needed

From the repository root:

```powershell
python experiments/finalize_evaluation.py
```

Then run the results notebook. This reapplies saved review decisions and rebuilds metrics. It costs nothing and does not rerun agents or generate new judgements.

### Share with teammates

The final results and saved review inputs are included as ordinary files in Git. Teammates can clone the repository, read the [findings](../output/final_evaluation_20261024/findings.md), run the notebooks or use the rebuild command above. Temporary working files remain ignored.

## How the evaluation works

**Saved agent runs -> factual labels -> review corrections -> metrics and charts.**

The LLM judge checks each output against the evidence and private error description. Review corrections are saved separately. Python calculates rates from those labels.

Read [evaluation.md](evaluation.md) for metric definitions and review rules. FAR needs evidence that the Trader relied on an error; accepting an unresolved error is a separate metric. Unknown labels are excluded from rates and reported alongside them.

## How to validate the judge labels

To inspect the completed review, use [review_sample.ipynb](../experiments/review_sample.ipynb).

For a separate independent human check, use [check_judge_labels.ipynb](../experiments/check_judge_labels.ipynb): read the evidence, record labels and a short reason, save, then compare with the judge. Run it one cell at a time and record earlier exposure to the labels. This additional check is not needed to display current results; independent human validation has not been completed.

## Run a new experiment

Follow the [fixed study configuration and commands](experiment-config.md#full-study-plan-fixed-on-24-october-2026), using new output folders. Run the agents, export their records, review the labels, then calculate metrics. The finalizer above only rebuilds the completed October study.

The main study compares four architectures with neutral wording. Confidence wording and reviewer disagreement are separate supplementary tests. Keep settings fixed within a comparison and preserve failed attempts.
