# Final evaluation: saved executions with evidence-review corrections

## Evaluation 1 (neutral tone)

Known outcomes use their own denominators. Pending labels and failed runs are not successes.

ACCEPT/REJECT assesses report support. BUY/HOLD/SELL is a separate investment action; HOLD does not mean REJECT.

| architecture | detection | correction after detection | resolution | accepted unresolved | FAR | TAR | challenges on initial controls | fully scored flawed | failed |
|---|---|---|---|---|---|---|---|---|---|
| baseline | n/a | n/a | 0.00 [0.00,0.39] (n=6) | 0.83 [0.44,0.97] (n=6) | 0.25 [0.05,0.70] (n=4) | 1.00 [0.61,1.00] (n=6) | n/a | 4/6 | 0 |
| debate | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0/0 | 0 |
| verification | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0/0 | 0 |
| hybrid | 1.00 [0.51,1.00] (n=4) | 1.00 [0.51,1.00] (n=4) | 1.00 [0.51,1.00] (n=4) | 0.00 [0.00,0.49] (n=4) | 0.00 [0.00,0.49] (n=4) | 1.00 [0.61,1.00] (n=6) | 0.83 [0.44,0.97] (n=6) | 4/6 | 2 |

Detection coverage (flawed inputs only):

| architecture | assigned | completed | detected | missed | pending detection | failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 6 | 6 | n/a | n/a | n/a | 0 |
| debate | 0 | 0 | 0 | 0 | 0 | 0 |
| verification | 0 | 0 | 0 | 0 | 0 | 0 |
| hybrid | 6 | 4 | 4 | 0 | 0 | 2 |

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
| hybrid | 0.00 [0.00,0.30] (n=9) | 9/10 | 3 | 7 | 0 |

### FAR by failure category

| category | baseline | debate | verification | hybrid |
|---|---|---|---|---|
| arithmetic | n/a | n/a | n/a | n/a |
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

### Repeated neutral conditions

Not supplied. Tone differences alone cannot separate framing sensitivity from repeat variation.

## Efficiency

| architecture | runs | input tokens | output tokens | USD | mean latency ms |
|---|---:|---:|---:|---:|---:|
| baseline | 12 | 17767 | 2057 | 0.0000 | 6990 |
| hybrid | 10 | 123032 | 20659 | 0.0000 | 38358 |

Review is complete within the documented scope; remaining unknowns are reviewed ambiguities, not safe outcomes. These are secondary reviews, not independent human ground truth. Failed application runs are retained.
