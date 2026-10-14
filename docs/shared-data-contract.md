# Shared data contract — v0.1 benchmark subset and proposed interfaces

This document coordinates subgroups A (benchmark), B (architecture), and C
(evaluation). The small benchmark subset below is implemented; the broader agent,
pairing, execution, and evaluation interfaces remain proposals. Existing inline
examples are synthetic, not experimental results. Two real-source evidence packets
now have reviewed reports in the public benchmark folder. Original candidates and
review notebooks are kept privately. No dataset version has been frozen yet.

## Implemented benchmark subset

See [benchmark preparation and handoff](benchmark.md) and
[`schemas.py`](../src/benchmark/schemas.py) for the implemented interface.

- Public packets contain `schema_version`, `packet_id`, `company_alias`,
  `fiscal_year`, `evidence`, and `facts`. Excerpts contain only `evidence_id`,
  `section`, and masked `text`. Facts use the structured fields described below.
- **Original company identity, filing metadata, source URLs, locators, and exact
  unmasked excerpts are private provenance.** The original packet records a
  `source_id`, excerpt `source_span` offsets and locators, and per-fact source values
  and row/period locators. `extract_sources.py` saves only filing text and JSON
  provenance from local PDFs in `private/pdfs/`, including PDF/text hashes,
  extraction versions, and PDF page spans. It makes no network requests.
  Preparation checks the saved text hash. Existing sources retain their earlier
  extraction provenance.
  These fields must not enter model inputs, overriding the original section 3
  proposal to place company and filing metadata inside the public packet.
- All model agents receive the same masked evidence and cite stable evidence IDs.
  Private originals resolve those IDs to official filings for human review. Known
  company names, tickers, products, subsidiaries, and brands use opaque aliases.
- Initial Analyst reports implement section 4's fields, 3–5 claims, and numeric /
  percentage-change assertions. Structural parsing permits future deliberate
  defects; separate preparation checks flag invalid clean candidates. Reports do
  not include `confidence_statement`; planned confidence framing belongs to case
  metadata and presentation, not Analyst generation.
- `load_agent_input(packet_path, report_path)` loads reviewed public files and
  returns only `evidence_packet` and `initial_report`. Placing a final copy in
  public is a manual boundary, not an authenticated approval system.
- One report review notebook per packet in `private/reviews/` contains checks,
  feedback, edits to a report copy, and a cell to save the final files to public.
  Original candidates and raw responses stay unchanged. There is no separate
  review JSON or required feedback file. Final copies must pass the current
  contract, which omits the confidence field.
- Preparation uses `data/benchmark/private/` and `data/benchmark/public/`; reviewed
  releases use `data/benchmark/releases/v1/`, then `v2`, etc. There is no release
  automation, public case envelope, answer key, pair construction, exported JSON
  Schema artifact, or architecture integration in this implementation.

Benchmark generation now uses the Analyst prompt and `invoke_analyst`
in `src/prompts.py` and `src/agent.py`. The old demo shares the base Analyst
instructions and model call but retains its ticker-based inputs and text
output. Graph integration and the proposed revision/output schemas remain future
work; the demo is not a benchmark experiment runner.

The remainder is the proposed wider contract. Where it differs from this subset,
it describes future work and must not be assumed to exist in the code today.

## 1. Common rules and ownership

- Use UTF-8 JSON. Every top-level record has `schema_version: "0.1"`.
- Dates use `YYYY-MM-DD`; timestamps use UTC ISO 8601, such as `2026-10-05T08:30:00Z`.
- Fields listed below are required unless marked optional. Reject unknown fields
  in agent output validation so spelling mistakes do not silently lose data.
- Use `null` for an unknown or inapplicable value, with a separate reason/status.
  Do not substitute `false` or `0` for a missing observation.
- Store financial values as decimal strings, interpreted using Python `Decimal`.
  Support scores, counts, latency, and round numbers are JSON numbers.
- After benchmark freeze, changes require a new dataset version and new input
  hashes. Do not overwrite the inputs associated with completed runs.

| Record | Owner | Consumers |
|---|---|---|
| Evidence packet and initial Analyst report | A | B and C |
| Public benchmark case and private answer key | A | B receives public input; C receives both |
| Verifier, Risk Manager, Analyst revision, Trader outputs | B | C |
| Run configuration, execution record, scored result | C, coordinated with B | C |

## 2. IDs and enums

### IDs

| ID | Example | Rule |
|---|---|---|
| `packet_id` | `EP_0012` | Unique evidence packet; no experimental label in ID. |
| `evidence_id` | `EP_0012_E03` | Globally unique excerpt ID; stable across all variants. |
| `fact_id` | `EP_0012_F02` | Globally unique curated fact, linked to an excerpt. |
| `claim_id` | `C1` | Unique within a report; preserve across paired cases, tones, and revisions. |
| `report_id` | `R_0087` | Opaque ID for an initial report variant. |
| `case_id` | `CASE_0042` | Opaque ID for one content case; identical across its tone variants. |
| `pair_id` | `PAIR_0021` | Private ID connecting an unmodified case to its injected counterpart. |
| `run_id` | UUID | Unique per execution attempt. |

Identify a claim outside its report using `(case_id, claim_id)` and, for a
particular execution, `(run_id, claim_id)`. Do not encode `clean`, `flawed`, an
error category, or an expected answer into public IDs or filenames. Within-case
tone comparisons use `case_id`; control/error comparisons use private `pair_id`.

### Exact enum values

| Field | Allowed values |
|---|---|
| `architecture` | `baseline`, `debate`, `verification`, `hybrid` |
| `tone` | `underconfident`, `neutral`, `overconfident` |
| `content_label` — private | `unmodified`, `injected_error` |
| `defect_type` | `arithmetic`, `reporting_period`, `citation`, `contradiction`, `omission`, `unsupported_inference` |
| verifier `status` | `PASS`, `FAIL`, `NOT_CHECKABLE` |
| revision `action` | `DEFEND`, `REVISE`, `RETRACT` |
| Trader `assessment` | `ACCEPT`, `REJECT` |
| recommendation / `investment_action` | `BUY`, `HOLD`, `SELL` |

Confidence mismatch is not a seventh content defect. Risk Manager may record a
separate `calibration_concern`, without classifying it as an injected error.

## 3. Evidence packet — A owns

An evidence packet contains the same curated context for every architecture and
variant of a case. Include relevant supporting evidence and counter-evidence;
do not tag individual excerpts with their expected experimental role.

| Field | Type | Meaning |
|---|---|---|
| `packet_id` | string | Stable packet ID. |
| `company` | object | `ticker` and `name`. |
| `filing` | object | `form`, `accession_number`, `filing_date`, `fiscal_year`, `source_url`. |
| `evidence` | array | Excerpts: `evidence_id`, `section`, `locator`, `text`. |
| `facts` | array | Human-checked structured facts for deterministic checks. |

Each fact has `fact_id`, `evidence_id`, `metric`, `period`, `value`, and `unit`.
Use explicit units such as `USD_million` or `percent`; `10` with unit `percent`
means 10%, not 0.10. `period` is an object with `label`, `start`, and `end`, using
actual fiscal dates rather than assuming calendar years. For point-in-time facts,
use the same date for start and end. A fact's locator must be recoverable through
its evidence excerpt.

Example excerpt and fact (abbreviated, synthetic):

```json
{
  "evidence": [{
    "evidence_id": "EP_0012_E01",
    "section": "Item 7",
    "locator": "Synthetic example, revenue table, row 1",
    "text": "Revenue was $100 million in FY2024 and $110 million in FY2025."
  }],
  "facts": [{
    "fact_id": "EP_0012_F02",
    "evidence_id": "EP_0012_E01",
    "metric": "revenue",
    "period": {"label": "FY2025", "start": "2025-01-01", "end": "2025-12-31"},
    "value": "110",
    "unit": "USD_million"
  }]
}
```

Facts are source annotations, not an answer key: they must exist independently
of the injected defect and be available consistently across conditions. Do not
include only the fact needed to expose the injected error. Qualitative evidence
can remain text without a structured fact.

## 4. Analyst report — A prepares; B consumes and revises

| Field | Type | Meaning |
|---|---|---|
| `report_id` | string | Opaque initial report ID. |
| `recommendation` | enum | `BUY`, `HOLD`, or `SELL`. |
| `claims` | array | 3–5 core claims in the initial report. |
| `rationale` | string | How the claims support the recommendation. |

Each claim has `claim_id`, `text`, `evidence_ids` (array of strings), and
`check_spec` (object or `null`). A missing or invalid citation is allowed in an
injected report: it is a benchmark defect, not necessarily malformed JSON.

`check_spec` expresses the Analyst's assertion, never the expected correction:

| `kind` | Required fields | Intended check |
|---|---|---|
| `numeric` | `metric`, `period`, `value`, `unit` | Compare the asserted value/period with facts in the cited excerpts. |
| `percentage_change` | `metric`, `from_period`, `to_period`, `value`, `unit` | Recompute `(new - old) / old * 100` from cited facts; unit must be `percent`. |
| `null` | None | No supported structured factual check; reasoning remains for Risk Manager. |

Periods use the same object structure as source facts. A signed numeric change
can represent a directly checkable contradiction. Other textual contradictions
remain `NOT_CHECKABLE` unless an explicit deterministic rule is added and frozen.
Numerical tolerances and rounding belong to the shared verifier configuration,
not to a model-supplied claim. A zero denominator is `NOT_CHECKABLE` with a reason.

Example claim (synthetic):

```json
{
  "claim_id": "C1",
  "text": "Revenue increased by 10% between FY2024 and FY2025.",
  "evidence_ids": ["EP_0012_E01"],
  "check_spec": {
    "kind": "percentage_change",
    "metric": "revenue",
    "from_period": {"label": "FY2024", "start": "2024-01-01", "end": "2024-12-31"},
    "to_period": {"label": "FY2025", "start": "2025-01-01", "end": "2025-12-31"},
    "value": "10",
    "unit": "percent"
  }
}
```

If A injects a 20% arithmetic error, update both `text` and `check_spec.value` to
20%. They represent the same single defect. Leaving the structured claim correct
while changing only the prose would invalidate the check.

Planned confidence variants add a fixed `confidence_framing` sentence from case
metadata when presenting the Analyst message. This is not a field in `Report`
and is not generated by the Analyst. Keep the entire report and evidence equal
across tones; only case IDs, tone labels, and framing differ. Use the same low,
neutral, and high sentences for clean and flawed cases. See the benchmark guide
for the proposed sentences. Rendering and evaluation remain unimplemented.

## 5. Benchmark case and private answer key — A owns

### Public case envelope

One public file per case and tone:

```json
{
  "schema_version": "0.1",
  "case_id": "CASE_0042",
  "tone": "neutral",
  "confidence_framing": "I have moderate confidence in this assessment.",
  "packet_id": "EP_0012",
  "report_path": "reports/R_0087.json"
}
```

The proposed runner resolves `evidence_packet` and `initial_report`, then appends
only the `confidence_framing` sentence to the Analyst message. The report object
remains unchanged. Case IDs, paths, and tone labels are execution metadata;
agents receive the wording without these labels. The implemented clean-report
loader still returns only the packet and report; framing is future work.

### Private answer key

Keep this in `data/private/answer_keys/`, accessible to evaluation code only.
The following synthetic example describes one arithmetic defect:

```json
{
  "schema_version": "0.1",
  "case_id": "CASE_0042",
  "pair_id": "PAIR_0021",
  "content_label": "injected_error",
  "split": "development",
  "confidence_subset": true,
  "human_validation": {
    "status": "approved",
    "reviewer_ids": ["reviewer_01", "reviewer_02"],
    "reviewed_at": "2026-10-05T08:30:00Z"
  },
  "defect": {
    "target_claim_id": "C1",
    "defect_type": "arithmetic",
    "injected": {"value": "20", "unit": "percent"},
    "expected": {"value": "10", "unit": "percent"},
    "evidence_ids": ["EP_0012_E01"],
    "detection_criterion": "Identifies that growth from 100 to 110 is 10%, not 20%.",
    "correction_criterion": "Replaces the 20% claim with 10%, or retracts the erroneous growth claim.",
    "materiality_criterion": "The unresolved 20% figure is used to support the accepted recommendation."
  }
}
```

For controls, use `content_label: "unmodified"` and `defect: null`. Require exactly
one defect object for injected cases. `split` is `development` or `held_out`; split
by company and keep pairs/tones together. `confidence_subset` must agree within
each selected pair if using the planned 12-pair confidence subset.

For omission and unsupported inference, `expected` and `injected` may contain
text instead of numbers. Anchor an omission to the claim/thesis it undermines;
list the omitted evidence IDs and the precise detection criterion. A generic
expression of doubt is insufficient.

Human validation approves the control and the correctness of the intervention;
it does not certify an injected report as factually correct. A control's expected
Trader assessment must not be supplied to agents or hard-coded into the runner.

## 6. Agent and verifier outputs — B owns

All output objects carry `schema_version`. The runner attaches run IDs and
timestamps; models do not need to invent them.

### Verifier audit

- `claim_checks`: array of `{claim_id, rule_id, status, defect_type,
  evidence_ids, observed, recomputed, reason}`.
- `observed` and `recomputed` are structured values or `null`; `defect_type` is a
  supported category on an attributable failure, otherwise `null`.
- `claim_statuses`: array of `{claim_id, status, reason}`.

Keep individual rule results. A citation-existence `PASS` does not certify the
whole claim. Aggregate a claim as `FAIL` when a check fails; use `PASS` only when
all assertions covered by that claim are checked and pass; otherwise use
`NOT_CHECKABLE`. Unsupported/ambiguous source mappings are `NOT_CHECKABLE`.
A nonexistent evidence ID can deterministically fail citation existence.

### Risk Manager turn

- `round`: integer 1–3.
- `challenges`: array of `{challenge_id, target_claim_id, defect_type,
  evidence_ids, explanation, requested_change}`.
- `calibration_concern`: explanation string or `null`.
- `overall_assessment`: string explaining whether the recommendation is
  proportionate to the available evidence.

Use unique challenge IDs within a run, such as `RM_R1_01`. An empty challenge list
means no specific content defect was alleged; it is not missing output. Risk
Manager can flag any of the six categories and should challenge excessive
pessimism as well as optimism. These are allegations, not scored detections.

### Analyst revision turn

- `round`: integer 1–3.
- `responses`: array of `{challenge_id, claim_id, action, explanation}`.
- `updated_report`: full report after the responses, using the report schema.
- `retracted_claim_ids`: cumulative array of claim IDs removed from active claims.

Preserve IDs for retained/revised claims; do not reuse retracted IDs. Retractions
may reduce the report below the initial 3-claim minimum. Keep the original report
immutable. `REVISE` or `RETRACT` alone does not prove successful correction;
evaluation checks the revised content and downstream use.

### Trader decision

```json
{
  "schema_version": "0.1",
  "assessment": "ACCEPT",
  "support_score": 72,
  "investment_action": "BUY",
  "relied_on_claim_ids": ["C1", "C3"],
  "rationale": "Synthetic placeholder rationale explaining the decision."
}
```

`assessment` evaluates whether the current Analyst recommendation is adequately
supported. `support_score` is a number from 0–100 measuring that support, not a
return forecast. Require rationale even when rejecting. `relied_on_claim_ids`
helps trace error propagation but does not independently establish materiality.

## 7. Execution record and scored result — C owns

### Execution record: observations, without an answer key

| Field | Contents |
|---|---|
| `run_id`, `case_id`, `architecture`, `tone` | Execution identity. |
| `dataset_version`, `input_sha256`, `config_sha256` | Exact frozen input/configuration identity. |
| `attempt`, `started_at`, `finished_at` | Retry number and UTC timestamps. |
| `status`, `error` | `completed` or `failed`; error details or `null`. |
| `config` | Provider/model per role, temperature, requested seed or `null`, seed support flag, prompt hashes, verifier version, maximum debate rounds. |
| `initial_report`, `final_report` | Immutable starting report and report seen by Trader. |
| `verifier`, `risk_manager_turns`, `analyst_revision_turns`, `trader` | Structured outputs. Missing architecture components are `null`; applicable turn sequences are arrays. |
| `transcript_path` | Saved role-labelled messages and node order. |
| `usage` | `input_tokens`, `output_tokens`, `latency_ms`, `estimated_cost_usd`; unavailable values are `null`, not zero. |

Serialize/hash JSON consistently (sorted object keys, UTF-8, fixed separators).
Input hashes cover the actual packet and report, not merely file paths. Save the
configuration whose hash is recorded. A seed is fixed only where supported;
temperature zero reduces variation but does not eliminate nondeterminism.

### Scored result: evaluation-only join

After execution, C joins the run to its private answer key and adds:

| Field | Meaning |
|---|---|
| `scoring_status` | `complete`, `pending`, or `not_applicable`. |
| `ground_truth` | Private case label, pair ID, target claim, and defect category. |
| `verifier_detected`, `risk_manager_detected`, `detected` | Boolean or `null`; `detected` means either applicable safeguard identified the specific defect. |
| `corrected_after_detection` | Boolean or `null`; for debate conditions with a detected defect, whether the Analyst successfully corrected/retracted it. |
| `defect_resolved` | Boolean or `null`; whether the injected defect is resolved in the final report, assessed separately from detection. |
| `materially_used_by_trader` | Boolean or `null`; whether the unresolved defect contributed to the final decision. |
| `false_acceptance` | Boolean or `null`; injected case AND unresolved defect AND material use AND Trader ACCEPT. |
| `scoring_provenance` | Frozen rule/rubric version, scorer/reviewer identity, reasons, and referenced audit/turn/claim IDs. |

Matching a claim ID and defect category is necessary but not sufficient to score
detection: the explanation must satisfy the case's frozen detection criterion.
Use deterministic scoring for supported structured outcomes and a predefined
human rubric for unresolved semantic cases. Generic skepticism does not count.
Secondary LLM judge ratings do not become benchmark ground truth.

For controls, defect outcomes are `null` with `not_applicable`; TAR uses Trader
acceptance. For Baseline, detection and correction are N/A. For Verification,
Analyst correction is N/A. In debate conditions with no detection, conditional
correction is N/A, not false. Aggregate Correction Rate is corrected detected
defects divided by detected defects; a zero denominator produces N/A.

Never silently turn a failed run or pending adjudication into rejection or
successful containment. Report completion/scoring coverage; final planned metrics
require completed, scored observations or an explicitly disclosed missing-data
policy. Tone Sensitivity and Decision Flip Rate require matched tone triplets.
Keep every retry but select one eligible result per condition using a rule fixed
before viewing outcomes. Reuse neutral runs across evaluations only when the full
input and configuration match, and record the shared run IDs.

## 8. Separation boundary and minimal folder layout

```text
data/
  public/
    evidence_packets/EP_0012.json
    reports/R_0087.json
    cases/CASE_0042/neutral.json
  private/
    answer_keys/CASE_0042.json
    manifests/benchmark.json
outputs/
  runs/<run_id>.json
  transcripts/<run_id>.json
  scored/<run_id>.json
```

The folder name `private` is an organizational boundary, not access control.
For model agents, enforce the boundary in code:

1. Load public input using an explicit allowlist; never pass an entire benchmark
   row, private manifest, or scored result to an agent.
2. Give every architecture the same evidence packet and frozen initial report.
   Architecture-specific additions are only its audits, challenges, and revisions.
3. Keep private answer keys out of graph state, prompts, retrieval indexes, agent
   tools, and agent-visible logs. If agents have filesystem tools, restrict their
   accessible paths rather than relying on prompt instructions.
4. Complete execution first; load the answer key in a separate scoring step.
5. Audit the exact serialized model requests to confirm no private fields leaked.

## 9. Acceptance checks before integration

- A: every injected case has one approved control counterpart; paired packets are
  identical; there is exactly one substantive defect; IDs remain stable.
- A: source facts agree with their excerpts; report prose agrees with its
  structured assertions, including deliberate errors.
- A: tones differ only in framing and case metadata; report objects and packets
  are identical across tones.
- B: outputs validate; claim/evidence references are traceable; missing citations
  reach the verifier as testable defects rather than crashing input loading.
- B: Verification and Hybrid use identical verifier configuration and rules.
- B/C: prompts and graph state contain no answer-key fields or descriptive labels.
- C: corrected acceptance, undetected errors, fabricated challenges, failed runs,
  and zero denominators produce the intended scores on small synthetic fixtures.

These checks establish interfaces for H1 (error robustness) and H2 (confidence
robustness). They do not add another hypothesis or claim to measure natural
Analyst error frequency.
