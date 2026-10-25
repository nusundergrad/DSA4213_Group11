# Evaluation report

## Evaluation 1 (neutral tone)

Known outcomes use their own denominators. Pending labels and failed runs are not successes.

ACCEPT/REJECT assesses report support. BUY/HOLD/SELL is a separate investment action; HOLD does not mean REJECT.

| architecture | detection | correction after detection | resolution | accepted unresolved | FAR | TAR | challenges on initial controls | fully scored flawed | failed |
|---|---|---|---|---|---|---|---|---|---|
| baseline | n/a | n/a | 0.00 [0.00,0.04] (n=90) | 0.82 [0.73,0.89] (n=90) | 0.79 [0.69,0.87] (n=77) | 1.00 [0.80,1.00] (n=15) | n/a | 77/90 | 0 |
| debate | 0.00 [0.00,0.24] (n=12) | n/a | 0.93 [0.81,0.98] (n=42) | 0.07 [0.02,0.19] (n=42) | 0.03 [0.00,0.13] (n=40) | 1.00 [0.77,1.00] (n=13) | 1.00 [0.77,1.00] (n=13) | 2/90 | 10 |
| verification | 0.34 [0.25,0.44] (n=89) | n/a | 0.00 [0.00,0.04] (n=89) | 0.52 [0.41,0.62] (n=89) | 0.39 [0.29,0.51] (n=71) | 1.00 [0.80,1.00] (n=15) | n/a | 71/90 | 1 |
| hybrid | 0.71 [0.56,0.83] (n=42) | 1.00 [0.87,1.00] (n=25) | 0.86 [0.73,0.93] (n=49) | 0.14 [0.07,0.26] (n=50) | 0.02 [0.00,0.12] (n=44) | 1.00 [0.78,1.00] (n=14) | 0.50 [0.27,0.73] (n=14) | 26/90 | 5 |

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
| debate | n/a | 0/95 | 18 | 57 | 20 |
| verification | n/a | 0/104 | 11 | 74 | 19 |
| hybrid | n/a | 0/100 | 12 | 68 | 20 |

### FAR by failure category

| category | baseline | debate | verification | hybrid |
|---|---|---|---|---|
| arithmetic | 0.93 (n=15) | 0.00 (n=9) | 0.00 (n=15) | 0.00 (n=14) |
| reporting_period | 1.00 (n=15) | 0.00 (n=14) | 0.00 (n=15) | 0.00 (n=11) |
| citation_misattribution | 1.00 (n=14) | 0.00 (n=8) | 1.00 (n=11) | 0.00 (n=9) |
| direct_factual_contradiction | 0.93 (n=15) | 0.00 (n=4) | 0.92 (n=13) | 0.00 (n=5) |
| material_omission | 1.00 (n=4) | 1.00 (n=1) | 1.00 (n=3) | 1.00 (n=1) |
| unsupported_inference | 0.00 (n=14) | 0.00 (n=4) | 0.14 (n=14) | 0.00 (n=4) |

### H1: hybrid vs each other architecture (paired, neutral tone)

- hybrid vs baseline: FAR 0.02 vs 0.91, diff -0.88 packet-bootstrap CI [-0.95,-0.83] (14 packets); TAR 1.00 vs 1.00 (14 packets)
- hybrid vs debate: FAR 0.00 vs 0.00, diff +0.00 packet-bootstrap CI [+0.00,+0.00] (14 packets); TAR 1.00 vs 1.00 (12 packets)
- hybrid vs verification: FAR 0.02 vs 0.29, diff -0.27 packet-bootstrap CI [-0.36,-0.16] (14 packets); TAR 1.00 vs 1.00 (14 packets)

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
| debate | 95 | 1229273 | 215481 | 0.0000 | 60743 |
| verification | 104 | 174651 | 18523 | 0.0000 | 7844 |
| hybrid | 100 | 1277913 | 186866 | 0.0000 | 49099 |
