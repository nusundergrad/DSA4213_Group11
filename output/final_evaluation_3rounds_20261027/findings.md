# Three-round findings

All four architectures use the same masked benchmark. Debate and hybrid use three Risk Manager-Analyst rounds; Trader does not receive the source packet.

## Execution

| Batch | Assigned | First-pass completed | Recovery attempts | Selected completed | Selected failed |
|---|---:|---:|---:|---:|---:|
| main_study_3rounds | 420 | 403 | 9 | 411 | 9 |
| confidence_study_3rounds | 72 | 62 | 4 | 65 | 7 |
| confidence_repeat_3rounds | 24 | 23 | 0 | 23 | 1 |

One explicit identical recovery was allowed for each prespecified transport/quota failure. Its result was selected even when it failed. Malformed or truncated model responses were retained without retries. All original attempts remain preserved.

## Main comparison

| Architecture | Detection | Resolution | Accepted unresolved | FAR | TAR | New errors |
|---|---|---|---|---|---|---|
| baseline | N/A | 0/90 (0.0%) | 77/90 (85.6%) | 17/35 (48.6%) | 15/15 (100.0%) | 4/105 (3.8%) |
| debate | 73/87 (83.9%) | 71/87 (81.6%) | 16/87 (18.4%) | 2/73 (2.7%) | 15/15 (100.0%) | 12/101 (11.9%) |
| verification | 30/90 (33.3%) | 0/90 (0.0%) | 54/90 (60.0%) | 3/52 (5.8%) | 15/15 (100.0%) | 1/105 (1.0%) |
| hybrid | 70/85 (82.4%) | 68/85 (80.0%) | 15/85 (17.6%) | 0/70 (0.0%) | 14/14 (100.0%) | 3/98 (3.1%) |

Rates show numerator / known outcomes. Unknown labels and execution failures remain separate; all architectures were assigned 90 flawed and 15 clean conditions.

FAR additionally requires expressed reliance on the erroneous part. Acceptance of an unresolved error is broader. TAR concerns a clean initial input and does not certify that later revisions stayed error-free.

Use the [main report](main_study_3rounds/findings.md) for matched comparisons and packet-bootstrap intervals. Related error variants are not independent companies.

## What the results show

- Debate and hybrid resolve about four-fifths of completed flawed inputs. Their similar resolution rates do not establish that hybrid is better at correction.
- Verification detects all completed arithmetic and period errors (30/30), but does not rewrite reports. The Trader still accepts 5/30 of these flagged reports. Its 0% resolution is a consequence of this architecture.
- Omissions remain the main weakness: debate restores 3/15 and hybrid 1/15. All 12 remaining debate omissions and 14 remaining hybrid omissions are accepted. Correct retained facts can hide missing counter-evidence even when the reviewer sees the packet.
- Hybrid introduces fewer identified new errors than debate (3/98 versus 12/101 known labels). This is a descriptive result from one model and 15 packets, not proof of general superiority.
- Hybrid has zero known FAR events, but 15 completed flawed cases have unknown reliance and 5 failed. Its all-assigned FAR bounds are 0/90 to 20/90. An uncertain label does not establish safety.
- All completed main-study clean inputs were accepted. That measures input acceptance; debate can still introduce a new error in a clean control.

Examples for the presentation:

| Case | Observation | Interpretation |
|---|---|---|
| EP_0002, arithmetic, baseline | Trader uses the injected 24.93% revenue growth to justify ACCEPT/HOLD; the correct growth is 14.93%. | HOLD can still propagate an error. |
| EP_0001, citation error, debate | The citation is repaired, but the final report attributes 13% Services growth to the FY2025 filing column, which actually says 14%. | Resolving the injected defect does not certify the rest of the revision. |
| EP_0012, omission, hybrid | Three reviews report no remaining defect while positive downstream earnings growth remains omitted. | Repeated agreement can miss missing counter-evidence. |

## Confidence and reviewer challenges

The [confidence report](confidence_study_3rounds/findings.md) compares fixed low/high wording against neutral and an identical neutral repeat. The notebook also restricts all comparisons to cases completed in all four conditions. Support scores are uncalibrated.

On cases completed in all four conditions:

| Architecture | Comparison with neutral | Matched cases | Verdict flips | Mean support change |
|---|---|---:|---:|---:|
| baseline | underconfident | 12 | 1 | -5.00 |
| baseline | overconfident | 12 | 0 | +9.58 |
| baseline | neutral_repeat | 12 | 0 | +0.42 |
| hybrid | underconfident | 9 | 1 | -11.11 |
| hybrid | overconfident | 9 | 0 | +2.78 |
| hybrid | neutral_repeat | 9 | 0 | -1.67 |

Low confidence changes one baseline verdict from ACCEPT to REJECT on an unresolved period error (EP_0006). It also changes one hybrid verdict to REJECT on a clean EP_0006 input, where revisions create rounding/specification disagreements. High confidence causes no verdict flips on the matched cases; neither do neutral repeats. These results show score sensitivity and rare verdict changes, not a reliable general persuasion effect.

Confidence acts through the full architecture: hybrid may revise the report before the Trader decides. A verdict change does not by itself isolate Trader persuasion or show improvement.

The fixed-report disagreement example in `src/justification.ipynb` is separate. It challenges the Risk Manager, not the Trader. Its two exploratory examples do not estimate a population failure rate.

## Review and limitations

Saved primary judge labels were cross-checked against source evidence using a second model pass, deterministic numerical checks and recorded adjudications. The cross-check uses the application model family, so correlated errors remain possible. Model agreement is not ground truth or independent human validation.

Positive errors have source references and output quotes. Semantic uncertainty remains null. Rounded filing percentages, calculated assertions and verifier interface failures are distinguished; see `uncertain.json` and the review notes.

The previous one-round results remain preserved. This is not an isolated test of round count: turn instructions and message handling also changed.

Cumulative key usage after the recovery judging was **$8.89**. The additional paid judge allowance consumed was about **$0.07**; the application and secondary cross-check used the free model. Evaluation spending is separate from the application efficiency table.
