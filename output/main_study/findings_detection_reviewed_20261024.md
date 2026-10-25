Detection review: saved Risk Manager challenges and overall assessments were reviewed by the assistant against the frozen injected-defect criteria. These are assistant judgments, not independent human adjudication. Agent outputs and benchmark inputs are unchanged. Resolution, reliance and new-error judgments are unchanged; detection-dependent metrics are recomputed. The EP_0008 contradiction key does not match the actual edited assertion; its debate/hybrid detection labels remain uncertain. Resolution, material reliance and new-error review remain incomplete. See [review notes](eval_detection_reviewed_20261024/detection_review.json) and [review protocol](eval_detection_reviewed_20261024/review_protocol.json).

# Evaluation report

## Evaluation 1 (neutral tone)

Known outcomes use their own denominators. Pending labels and failed runs are not successes.

ACCEPT/REJECT assesses report support. BUY/HOLD/SELL is a separate investment action; HOLD does not mean REJECT.

| architecture | detection | correction after detection | resolution | accepted unresolved | FAR | TAR | challenges on initial controls | fully scored flawed | failed |
|---|---|---|---|---|---|---|---|---|---|
| baseline | n/a | n/a | 0.00 [0.00,0.04] (n=90) | 0.82 [0.73,0.89] (n=90) | 0.79 [0.69,0.87] (n=77) | 1.00 [0.80,1.00] (n=15) | n/a | 77/90 | 0 |
| debate | 0.87 [0.79,0.93] (n=86) | 1.00 [0.91,1.00] (n=40) | 0.93 [0.81,0.98] (n=43) | 0.07 [0.02,0.19] (n=43) | 0.02 [0.00,0.13] (n=41) | 1.00 [0.78,1.00] (n=14) | 1.00 [0.78,1.00] (n=14) | 41/90 | 4 |
| verification | 0.33 [0.24,0.44] (n=90) | n/a | 0.00 [0.00,0.04] (n=90) | 0.52 [0.42,0.62] (n=90) | 0.39 [0.29,0.51] (n=71) | 1.00 [0.80,1.00] (n=15) | n/a | 71/90 | 0 |
| hybrid | 0.89 [0.80,0.94] (n=87) | 1.00 [0.92,1.00] (n=42) | 0.86 [0.73,0.93] (n=49) | 0.14 [0.07,0.26] (n=50) | 0.02 [0.00,0.12] (n=44) | 1.00 [0.80,1.00] (n=15) | 0.53 [0.30,0.75] (n=15) | 43/90 | 2 |

Detection coverage (flawed inputs only):

| architecture | assigned | completed | detected | missed | pending detection | failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 90 | 90 | n/a | n/a | n/a | 0 |
| debate | 90 | 87 | 75 | 11 | 1 | 3 |
| verification | 90 | 90 | 30 | 60 | 0 | 0 |
| hybrid | 90 | 88 | 77 | 10 | 1 | 2 |

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
| baseline | n/a | 0/105 | 17 | 69 | 19 |
| debate | n/a | 0/101 | 18 | 62 | 21 |
| verification | n/a | 0/105 | 12 | 74 | 19 |
| hybrid | n/a | 0/103 | 14 | 69 | 20 |

### FAR by failure category

| category | baseline | debate | verification | hybrid |
|---|---|---|---|---|
| arithmetic | 0.93 (n=15) | 0.00 (n=10) | 0.00 (n=15) | 0.00 (n=14) |
| reporting_period | 1.00 (n=15) | 0.00 (n=14) | 0.00 (n=15) | 0.00 (n=11) |
| citation_misattribution | 1.00 (n=14) | 0.00 (n=8) | 1.00 (n=11) | 0.00 (n=9) |
| direct_factual_contradiction | 0.93 (n=15) | 0.00 (n=4) | 0.92 (n=13) | 0.00 (n=5) |
| material_omission | 1.00 (n=4) | 1.00 (n=1) | 1.00 (n=3) | 1.00 (n=1) |
| unsupported_inference | 0.00 (n=14) | 0.00 (n=4) | 0.14 (n=14) | 0.00 (n=4) |

### H1: hybrid vs each other architecture (paired, neutral tone)

- hybrid vs baseline: FAR 0.02 vs 0.91, diff -0.88 packet-bootstrap CI [-0.95,-0.83] (14 packets); TAR 1.00 vs 1.00 (15 packets)
- hybrid vs debate: FAR 0.00 vs 0.00, diff +0.00 packet-bootstrap CI [+0.00,+0.00] (14 packets); TAR 1.00 vs 1.00 (14 packets)
- hybrid vs verification: FAR 0.02 vs 0.29, diff -0.27 packet-bootstrap CI [-0.36,-0.16] (14 packets); TAR 1.00 vs 1.00 (15 packets)

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
