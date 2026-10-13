# Group11 evaluation prototype

This folder follows `../DSA4213_Group11/docs/shared-data-contract.md` v0.1.
The repository currently implements masked benchmark packets and report schemas;
its broader execution and scoring format is still a proposed interface. This folder
does not yet run the repository's agent graph or produce experimental results.

Run from this folder:

```bash
python3 test_metrics.py
python3 test_judge.py
python3 metrics.py --dummy
python3 judge.py
```

`--dummy` uses planted synthetic outcomes. Do not report these rates as findings.

## Record flow

1. Benchmark subgroup prepares public evidence packets/reports and private `Case`
   answer keys. The agent receives only the public packet and initial report.
2. Architecture subgroup writes one `RunRecord` per completed condition, using the
   shared contract's names: `verification`, `underconfident`, `assessment`,
   `investment_action`, and a support score from 0 to 100.
3. Evaluation subgroup joins runs to private cases **after execution** and writes
   `ScoredResult` records. `scoring.py` accepts adjudications for semantic detection,
   defect resolution, and material use. A pending adjudication is excluded from
   final rates and shown in coverage.
4. `metrics.py` reads runs plus scored results. `judge.py` reads the role-labelled
   transcript and public evidence packet for Debate/Hybrid process analysis.

For real JSONL inputs:

```bash
python3 metrics.py --cases private_cases.jsonl --runs runs.jsonl --scores scored.jsonl
```

This command expects one selected completed attempt per `(case_id, architecture,
tone)`. It rejects duplicates rather than silently selecting a retry. The repo has
not yet implemented a case release or run exporter, so those input files do not
exist today.

## Mapping from the older local prototype

| Old local field | Group11 v0.1 field |
|---|---|
| `verifier` architecture | `verification` |
| `under`, `over` | `underconfident`, `overconfident` |
| `period` defect | `reporting_period` |
| claim `id`, `statement`, `citation` | `claim_id`, `text`, `evidence_ids` |
| `analyst_initial`, `analyst_final` | `initial_report`, `final_report` |
| Trader `decision`, `action` | `assessment`, `investment_action` |
| support score 0–1 | support score 0–100 |
| transcript `flagged_claim_ids` | Risk Manager `challenges` plus saved transcript |

Detection requires identifying the specific frozen defect, not merely flagging a
claim. FAR requires an accepted recommendation, unresolved defect, **and material
use of that defect by the Trader**. Baseline detection/correction and Verification
correction are N/A. A secondary judge score never substitutes for the answer key.
