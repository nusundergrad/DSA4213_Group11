# Final evaluation: saved executions with evidence-review corrections

## Evaluation 1 (neutral tone)

Known outcomes use their own denominators. Pending labels and failed runs are not successes.

ACCEPT/REJECT assesses report support. BUY/HOLD/SELL is a separate investment action; HOLD does not mean REJECT.

| architecture | detection | correction after detection | resolution | accepted unresolved | FAR | TAR | challenges on initial controls | fully scored flawed | failed |
|---|---|---|---|---|---|---|---|---|---|
| baseline | n/a | n/a | 0.00 [0.00,0.04] (n=90) | 0.82 [0.73,0.89] (n=90) | 0.21 [0.13,0.33] (n=66) | 1.00 [0.80,1.00] (n=15) | n/a | 66/90 | 0 |
| debate | 0.91 [0.83,0.95] (n=87) | 0.95 [0.88,0.98] (n=79) | 0.86 [0.77,0.92] (n=87) | 0.14 [0.08,0.23] (n=87) | 0.00 [0.00,0.04] (n=83) | 1.00 [0.78,1.00] (n=14) | 1.00 [0.78,1.00] (n=14) | 83/90 | 4 |
| verification | 0.33 [0.24,0.44] (n=90) | n/a | 0.00 [0.00,0.04] (n=90) | 0.52 [0.42,0.62] (n=90) | 0.01 [0.00,0.07] (n=81) | 1.00 [0.80,1.00] (n=15) | n/a | 81/90 | 0 |
| hybrid | 0.89 [0.80,0.94] (n=88) | 0.99 [0.93,1.00] (n=78) | 0.88 [0.79,0.93] (n=88) | 0.12 [0.07,0.21] (n=88) | 0.00 [0.00,0.04] (n=82) | 1.00 [0.80,1.00] (n=15) | 0.53 [0.30,0.75] (n=15) | 82/90 | 2 |

Detection coverage (flawed inputs only):

| architecture | assigned | completed | detected | missed | pending detection | failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 90 | 90 | n/a | n/a | n/a | 0 |
| debate | 90 | 87 | 79 | 8 | 0 | 3 |
| verification | 90 | 90 | 30 | 60 | 0 | 0 |
| hybrid | 90 | 88 | 78 | 10 | 0 | 2 |

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
| baseline | 0.01 [0.00,0.05] (n=105) | 105/105 | 17 | 69 | 19 |
| debate | 0.11 [0.06,0.19] (n=99) | 99/101 | 18 | 62 | 21 |
| verification | 0.00 [0.00,0.04] (n=105) | 105/105 | 12 | 74 | 19 |
| hybrid | 0.04 [0.02,0.10] (n=101) | 101/103 | 14 | 69 | 20 |

### FAR by failure category

| category | baseline | debate | verification | hybrid |
|---|---|---|---|---|
| arithmetic | 0.83 (n=12) | 0.00 (n=14) | 0.00 (n=15) | 0.00 (n=15) |
| reporting_period | 0.75 (n=4) | 0.00 (n=15) | 0.00 (n=15) | 0.00 (n=15) |
| citation_misattribution | 0.00 (n=15) | 0.00 (n=15) | 0.00 (n=15) | 0.00 (n=14) |
| direct_factual_contradiction | 0.00 (n=14) | 0.00 (n=15) | 0.00 (n=15) | 0.00 (n=15) |
| material_omission | 0.17 (n=6) | 0.00 (n=9) | 0.17 (n=6) | 0.00 (n=8) |
| unsupported_inference | 0.00 (n=15) | 0.00 (n=15) | 0.00 (n=15) | 0.00 (n=15) |

### H1: hybrid vs each other architecture (paired, neutral tone)

- hybrid vs baseline: FAR 0.00 vs 0.22, diff -0.22 packet-bootstrap CI [-0.28,-0.16] (15 packets); TAR 1.00 vs 1.00 (15 packets)
- hybrid vs debate: FAR 0.00 vs 0.00, diff +0.00 packet-bootstrap CI [+0.00,+0.00] (15 packets); TAR 1.00 vs 1.00 (14 packets)
- hybrid vs verification: FAR 0.00 vs 0.01, diff -0.01 packet-bootstrap CI [-0.04,+0.00] (15 packets); TAR 1.00 vs 1.00 (15 packets)

## Supplementary: tone changes from neutral (support scale 0-100)

Support scores are self-reported, not calibrated probabilities. Compare verdict flips and neutral repeats before attributing differences to tone.

| architecture | tone | n | mean support change | mean abs change | flip | dD | dC | dP |
|---|---|---:|---:|---:|---:|---:|---:|---:|

### Repeated neutral conditions

Not supplied. Tone differences alone cannot separate framing sensitivity from repeat variation.

## Efficiency

| architecture | runs | input tokens | output tokens | USD | mean latency ms |
|---|---:|---:|---:|---:|---:|
| baseline | 105 | 159590 | 19049 | 0.0000 | 7395 |
| debate | 101 | 1300470 | 226702 | 0.0000 | 59388 |
| verification | 105 | 176293 | 18676 | 0.0000 | 7814 |
| hybrid | 103 | 1317247 | 193776 | 0.0000 | 49033 |

Review is complete within the documented scope; remaining unknowns are reviewed ambiguities, not safe outcomes. These are secondary reviews, not independent human ground truth. Failed application runs are retained.
