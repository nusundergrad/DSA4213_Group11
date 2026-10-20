# Group11 evaluation prototype

This folder follows `../DSA4213_Group11/docs/shared-data-contract.md` v0.1.
The repository currently implements masked benchmark packets and report schemas;
its broader execution and scoring format is still a proposed interface. This folder
does not yet run the repository's agent graph or produce experimental results.

Run the tests from the repository root (`tests/conftest.py` puts `src/evaluation` on the path):

```bash
python -m pytest tests -q                 # benchmark + evaluation tests
python src/evaluation/metrics.py --dummy  # full synthetic report
python src/evaluation/judge.py            # judge smoke test (mock backend)
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
   `auto_scoring.py` fills in every adjudication that a rule can decide and leaves the rest `pending`
   (see below). `benchmark_cases.py` builds the answer keys from the benchmark's `private/pairs.json`.
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

## Answer keys and automatic scoring

```bash
python src/evaluation/benchmark_cases.py --out outputs/eval_private   # cases.jsonl + manifest.json (eval-only)
```

`benchmark_cases.py` turns the 6 reviewed pairs into 6 flawed `Case`s plus 2 controls (one per clean
report, because each clean report is reused by three flawed copies; the controls are not independent).
Case IDs are opaque. `load_agent_input_for` returns only the public packet and report.

`auto_scoring.auto_score_run(run, case, clean_report)` decides, by rule:

| Field | Rule | Otherwise |
|---|---|---|
| `verifier_detected` | FAIL on the target claim whose `defect_type` equals the frozen defect type; for `wrong_number`/`arithmetic`/`reporting_period` a bare FAIL status on the target also counts (the graph verifier only checks `check_spec` numbers and emits no type) | any other FAIL -> pending; no FAIL -> False |
| `defect_resolved` | target claim retracted, or its `check_spec` (else text) equals the clean claim -> True; unchanged from the initial claim -> False | any other edit -> pending |
| `materially_used_by_trader` | Trader REJECT -> False; ACCEPT and target in `relied_on_claim_ids` -> True | ACCEPT but not relied on -> pending (opt out with `unrelied_is_immaterial=True`) |
| `risk_manager_detected` | no challenge targets the claim -> False | right type and states an expected value/period -> only a *suggestion* (`rm_mode="accept"` to trust it); otherwise pending |

Semantic Risk Manager detection and reasoning-level defects still need a human (or a calibrated
judge) checking the case's `detection_criterion`. `pending_report(scores)` lists the workload.

## Graph output adapter

`src/evaluation/graph_adapter.py` converts `run_batch` records (`src/graph.py`) into `RunRecord`s:

```bash
python src/evaluation/graph_adapter.py output/ --out outputs/eval_runs   # runs.jsonl + scored.jsonl
```

It only reshapes data and never invents values. Mapping: `situation_1/2/3` -> `debate/verification/hybrid`;
`initial_report.report_id` -> `case_id`; `final_reports[-1]` -> `final_report`; messages -> role-labelled
`transcript`; verifier booleans -> `PASS`/`FAIL`. Several runs of one condition are an error unless
`--keep-latest`.

The graph now writes the structured fields the scoring needs: Risk Manager turns with `challenges`, Trader
`support_score` and `relied_on_claim_ids`, the run's `tone` and confidence sentence, `usage` (tokens and
latency), `config` (model, temperature, debate rounds), and `analyst_revision_turns` (edited, reverted and
retracted claim IDs). `situation_0` is the baseline. Records written before these changes still convert; their
missing fields leave the affected scores `pending`, never wrong.

Still not produced: verifier `claim_checks` (the defect type of a FAIL). `verifier_detected` therefore counts a
bare FAIL on the target only for `wrong_number`, `arithmetic` and `reporting_period`; any other FAIL is pending.
Cost is `null` unless the provider reports it, and tokens of rejected or retried responses are not counted.
