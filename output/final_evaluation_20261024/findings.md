# Final evaluation findings

The evaluation and documented review are complete. The same saved executions are used; no new model calls were made.
Main study: 414/420 completed; confidence: 70/72; neutral repeat: 22/24. All ten execution failures remain recorded.

| Architecture | Detection | Resolution | Accepted unresolved | FAR, known labels | FAR uncertain | TAR | New errors, known labels | New-error uncertain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | n/a | 0/90 | 74/90 | 14/66 | 24 | 15/15 | 1/105 | 0 |
| debate | 79/87 | 75/87 | 12/87 | 0/83 | 4 | 14/14 | 11/99 | 2 |
| verification | 30/90 | 0/90 | 47/90 | 1/81 | 9 | 15/15 | 0/105 | 0 |
| hybrid | 78/88 | 77/88 | 11/88 | 0/82 | 6 | 15/15 | 4/101 | 2 |

FAR requires expressed reliance on the erroneous part. Accepted unresolved only requires acceptance with the injected error still present. Unknown is not safe; TAR concerns initially clean inputs, not final-output correctness.

## Uncertainty over all 90 assigned flawed conditions

The bounds count unknown labels and failed executions as non-events at the lower bound and events at the upper bound. They are sensitivity bounds, not confidence intervals.

| Architecture | FAR lower bound | FAR upper bound |
|---|---:|---:|
| baseline | 15.6% | 42.2% |
| debate | 0.0% | 7.8% |
| verification | 1.1% | 11.1% |
| hybrid | 0.0% | 8.9% |

## Findings

- Debate and hybrid resolve most injected defects. Verification reduces acceptance of flawed reports without revising their content.
- Zero observed FAR among known debate/hybrid labels does not establish perfect safety. Accepted unresolved outputs and reviewed ambiguity remain.
- Correction can introduce a different error. The main study contains 16 identified new-error outputs and four uncertain cases. Examples include wrong filing percentages, acquisition-inclusive growth called organic, and unsupported higher-margin segment descriptions.
- This study does not establish a hybrid advantage over debate. Read the paired comparisons and their coverage in main_study/findings.md.

## Confidence with an identical neutral repeat

Use cases completed in all four conditions so tone and repeat comparisons share the same cases. Support scores are not calibrated probabilities.

| Architecture | Comparison | Matched cases | Verdict flips | Mean support change |
|---|---|---:|---:|---:|
| baseline | underconfident | 12 | 4 | -14.08 |
| baseline | overconfident | 12 | 0 | +8.83 |
| baseline | neutral_repeat | 12 | 0 | +0.00 |
| hybrid | underconfident | 10 | 0 | -7.00 |
| hybrid | overconfident | 10 | 0 | +2.00 |
| hybrid | neutral_repeat | 10 | 0 | +1.50 |

Low-confidence wording changes four baseline ACCEPTs to REJECTs: two clean and two flawed. High confidence and the neutral repeat change none. The fully matched hybrid subset has no verdict flips. This is a limited, mixed sensitivity result, not reliable manipulation or improvement.

## Review scope and limitations

The export applies 118 full-field sample reviews, all 162 accepted-unresolved reliance checks, all 31 omission-detection checks, and a screen of 506 outputs for discovered new-error families. The screen produced 111 candidate outputs; candidate text was inspected against the source packets. Unchanged fields retain the earlier judge labels.
This is secondary review, not independent human ground truth or exhaustive independent review of every field in every run. Genuine uncertainties remain recorded. There are 15 companies, related manufactured variants, short evidence packets, one application model and one debate round. EP_0006 has unequal arithmetic-error magnitudes in prose and its structured assertion. Results should be presented at this scope.

Use experiments/explore_results.ipynb for the tables, examples and charts. Run python experiments/finalize_evaluation.py to rebuild this export from the saved review decisions. Original exports and executions are preserved. Additional API cost: $0.
