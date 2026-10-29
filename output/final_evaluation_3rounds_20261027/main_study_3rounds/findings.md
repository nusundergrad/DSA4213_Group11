# Three-round evaluation

## Evaluation 1 (neutral tone)

Known outcomes use their own denominators. Pending labels and failed runs are not successes.

ACCEPT/REJECT assesses report support. BUY/HOLD/SELL is a separate investment action; HOLD does not mean REJECT.

| architecture | detection | correction after detection | resolution | accepted unresolved | FAR | TAR | challenges on initial controls | fully scored flawed | failed |
|---|---|---|---|---|---|---|---|---|---|
| baseline | n/a | n/a | 0.00 [0.00,0.04] (n=90) | 0.86 [0.77,0.91] (n=90) | 0.49 [0.33,0.64] (n=35) | 1.00 [0.80,1.00] (n=15) | n/a | 35/90 | 0 |
| debate | 0.84 [0.75,0.90] (n=87) | 0.97 [0.91,0.99] (n=73) | 0.82 [0.72,0.88] (n=87) | 0.18 [0.12,0.28] (n=87) | 0.03 [0.01,0.09] (n=73) | 1.00 [0.80,1.00] (n=15) | 0.47 [0.25,0.70] (n=15) | 73/90 | 3 |
| verification | 0.33 [0.24,0.44] (n=90) | n/a | 0.00 [0.00,0.04] (n=90) | 0.60 [0.50,0.70] (n=90) | 0.06 [0.02,0.16] (n=52) | 1.00 [0.80,1.00] (n=15) | n/a | 52/90 | 0 |
| hybrid | 0.82 [0.73,0.89] (n=85) | 0.97 [0.90,0.99] (n=70) | 0.80 [0.70,0.87] (n=85) | 0.18 [0.11,0.27] (n=85) | 0.00 [0.00,0.05] (n=70) | 1.00 [0.78,1.00] (n=14) | 0.29 [0.12,0.55] (n=14) | 70/90 | 6 |

Detection coverage (flawed inputs only):

| architecture | assigned | completed | detected | missed | pending detection | failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 90 | 90 | n/a | n/a | n/a | 0 |
| debate | 90 | 87 | 73 | 14 | 0 | 3 |
| verification | 90 | 90 | 30 | 60 | 0 | 0 |
| hybrid | 90 | 85 | 70 | 15 | 0 | 5 |

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
| baseline | 0.04 [0.01,0.09] (n=105) | 105/105 | 17 | 68 | 20 |
| debate | 0.12 [0.07,0.20] (n=101) | 101/102 | 17 | 64 | 21 |
| verification | 0.01 [0.00,0.05] (n=105) | 105/105 | 12 | 76 | 17 |
| hybrid | 0.03 [0.01,0.09] (n=98) | 98/99 | 12 | 66 | 21 |

### FAR by failure category

| category | baseline | debate | verification | hybrid |
|---|---|---|---|---|
| arithmetic | 0.92 (n=12) | 0.14 (n=14) | 0.00 (n=15) | 0.00 (n=13) |
| reporting_period | 1.00 (n=3) | 0.00 (n=14) | 0.00 (n=15) | 0.00 (n=14) |
| citation_misattribution | 0.00 (n=1) | 0.00 (n=14) | 0.00 (n=1) | 0.00 (n=13) |
| direct_factual_contradiction | 0.40 (n=5) | 0.00 (n=13) | 0.33 (n=6) | 0.00 (n=15) |
| material_omission | 1.00 (n=1) | 0.00 (n=3) | 1.00 (n=1) | 0.00 (n=1) |
| unsupported_inference | 0.00 (n=13) | 0.00 (n=15) | 0.00 (n=14) | 0.00 (n=14) |

### H1: hybrid vs each other architecture (paired, neutral tone)

- hybrid vs baseline: FAR 0.00 vs 0.50, diff -0.50 packet-bootstrap CI [-0.61,-0.39] (15 packets); TAR 1.00 vs 1.00 (14 packets)
- hybrid vs debate: FAR 0.00 vs 0.03, diff -0.03 packet-bootstrap CI [-0.07,+0.00] (15 packets); TAR 1.00 vs 1.00 (14 packets)
- hybrid vs verification: FAR 0.00 vs 0.06, diff -0.06 packet-bootstrap CI [-0.12,+0.00] (15 packets); TAR 1.00 vs 1.00 (14 packets)

## Supplementary: tone changes from neutral (support scale 0-100)

Support scores are self-reported, not calibrated probabilities. Compare verdict flips and neutral repeats before attributing differences to tone.

| architecture | tone | n | mean support change | mean abs change | flip | dD | dC | dP |
|---|---|---:|---:|---:|---:|---:|---:|---:|

### Repeated neutral conditions

Not supplied. Tone differences alone cannot separate framing sensitivity from repeat variation.

## Efficiency

| architecture | runs | input tokens | output tokens | USD | mean latency ms |
|---|---:|---:|---:|---:|---:|
| baseline | 105 | 163475 | 19312 | 0.0000 | 5145 |
| debate | 102 | 4109888 | 522763 | 0.0000 | 95071 |
| verification | 105 | 180178 | 18802 | 0.0000 | 4687 |
| hybrid | 99 | 3832577 | 454428 | 0.0000 | 78536 |
