# Final evaluation: saved executions with evidence-review corrections

## Evaluation 1 (neutral tone)

Known outcomes use their own denominators. Pending labels and failed runs are not successes.

ACCEPT/REJECT assesses report support. BUY/HOLD/SELL is a separate investment action; HOLD does not mean REJECT.

| architecture | detection | correction after detection | resolution | accepted unresolved | FAR | TAR | challenges on initial controls | fully scored flawed | failed |
|---|---|---|---|---|---|---|---|---|---|
| baseline | n/a | n/a | 0.00 [0.00,0.39] (n=6) | 0.83 [0.44,0.97] (n=6) | 0.25 [0.05,0.70] (n=4) | 1.00 [0.61,1.00] (n=6) | n/a | 4/6 | 0 |
| debate | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0/0 | 0 |
| verification | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0/0 | 0 |
| hybrid | 0.80 [0.38,0.96] (n=5) | 1.00 [0.51,1.00] (n=4) | 1.00 [0.57,1.00] (n=5) | 0.00 [0.00,0.43] (n=5) | 0.00 [0.00,0.43] (n=5) | 1.00 [0.61,1.00] (n=6) | 0.33 [0.10,0.70] (n=6) | 5/6 | 1 |

Detection coverage (flawed inputs only):

| architecture | assigned | completed | detected | missed | pending detection | failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 6 | 6 | n/a | n/a | n/a | 0 |
| debate | 0 | 0 | 0 | 0 | 0 | 0 |
| verification | 0 | 0 | 0 | 0 | 0 | 0 |
| hybrid | 6 | 5 | 4 | 1 | 0 | 1 |

Detection uses detected / (detected + missed). Pending labels are unreviewed or uncertain, not misses. Do not rank architectures using incomplete, different subsets; inspect coverage and compare matched cases.
Accepted unresolved counts ACCEPT with an unresolved injected defect, without requiring material reliance. REJECT or resolved means false; ACCEPT with unknown resolution stays unknown.
FAR additionally requires material reliance. Unknown reliance stays pending, even if a claim ID was cited. Review automatic reliance labels against the rationale.
TAR means acceptance when the input is a clean control; it does not establish that later revisions stayed correct. Resolution concerns the injected defect, not certification that no new error appeared.
Control challenges are an observed rate, not automatically false challenges; their validity needs review.
Per-rate Wilson intervals are descriptive case-level summaries. Paired difference intervals resample whole evidence packets; variants are not independent companies. No packet-bootstrap interval is estimated from one packet.

### New errors in final outputs (neutral tone)

Review final Analyst reports and Trader rationales against the initial input and evidence. Persisting injected errors are not newly introduced errors. Unknown reviews are excluded, not counted as error-free.

| architecture | new-error rate | reviewed / completed | BUY | HOLD | SELL |
|---|---|---|---:|---:|---:|
| baseline | 0.00 [0.00,0.24] (n=12) | 12/12 | 3 | 9 | 0 |
| debate | n/a | 0/0 | 0 | 0 | 0 |
| verification | n/a | 0/0 | 0 | 0 | 0 |
| hybrid | 0.00 [0.00,0.28] (n=10) | 10/11 | 3 | 8 | 0 |

### FAR by failure category

| category | baseline | debate | verification | hybrid |
|---|---|---|---|---|
| arithmetic | n/a | n/a | n/a | 0.00 (n=1) |
| reporting_period | 1.00 (n=1) | n/a | n/a | 0.00 (n=1) |
| citation_misattribution | 0.00 (n=1) | n/a | n/a | 0.00 (n=1) |
| direct_factual_contradiction | 0.00 (n=1) | n/a | n/a | 0.00 (n=1) |
| material_omission | n/a | n/a | n/a | 0.00 (n=1) |
| unsupported_inference | 0.00 (n=1) | n/a | n/a | n/a |

### H1: hybrid vs each other architecture (paired, neutral tone)

- hybrid vs baseline: FAR 0.00 vs 0.33, diff -0.33 packet-bootstrap CI [-1.00,+0.00] (3 packets); TAR 1.00 vs 1.00 (6 packets)
- hybrid vs debate: no overlapping scored cases
- hybrid vs verification: no overlapping scored cases

## Supplementary: tone changes from neutral (support scale 0-100)

Support scores are self-reported, not calibrated probabilities. Compare verdict flips and neutral repeats before attributing differences to tone.

| architecture | tone | n | mean support change | mean abs change | flip | dD | dC | dP |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | underconfident | 12 | -14.08 | 14.08 | 0.33 | n/a | n/a | -0.25 |
| baseline | overconfident | 12 | +8.83 | 8.83 | 0.00 | n/a | n/a | +0.00 |
| hybrid | underconfident | 11 | -7.27 | 7.27 | 0.00 | +0.00 | +0.00 | +0.00 |
| hybrid | overconfident | 11 | +1.82 | 1.82 | 0.00 | +0.20 | +0.00 | +0.00 |

### Repeated neutral conditions

| architecture | matched completed | verdict flip | support pairs | mean abs support change |
|---|---:|---|---:|---:|
| baseline | 12 | 0.00 [0.00,0.24] (n=12) | 12 | +0.00 |
| hybrid | 10 | 0.00 [0.00,0.28] (n=10) | 10 | +1.50 |

## Efficiency

| architecture | runs | input tokens | output tokens | USD | mean latency ms |
|---|---:|---:|---:|---:|---:|
| baseline | 36 | 53301 | 6151 | 0.0000 | 5318 |
| hybrid | 34 | 409925 | 64879 | 0.0000 | 39157 |

Review is complete within the documented scope; remaining unknowns are reviewed ambiguities, not safe outcomes. These are secondary reviews, not independent human ground truth. Failed application runs are retained.
