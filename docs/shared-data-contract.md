# Shared data contract — v0.1 benchmark subset and proposed interfaces

This document coordinates benchmark, architecture and evaluation work. On `testing`, the benchmark, graph runner and scoring pipeline are implemented; later sections also contain proposed extensions.
Current data: 15 packets, 15 clean reports and 90 flawed variants across six error types. The working dataset and preserved `releases/v1` snapshot must not be mixed.
See [the current evaluation rules](evaluation.md) and [execution commands](running-experiments.md) where older proposal examples differ.

Execution follows `main`'s information boundary: Analyst and Risk Manager receive masked evidence; Trader receives the current report, current verifier result and latest agent message, without the source packet or full discussion. Structured challenge/reliance fields enable evaluation. Actual Analyst revisions remain observable.

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
- Evidence-consuming agents receive the same masked packet and cite stable evidence IDs; the Trader uses only the analysis and verifier output supplied to it.
  Private originals resolve those IDs to official filings for human review. Known
  company names, tickers, products, subsidiaries, and brands use opaque aliases.
- Initial Analyst reports implement section 4's fields, 3–5 claims, and numeric /
  percentage-change assertions. Structural parsing permits future deliberate
  defects; separate preparation checks flag invalid clean candidates. Reports do
  not include `confidence_statement`; planned confidence framing belongs to case
  metadata and presentation, not Analyst generation.
- Numerical assertions now identify source facts: `numeric.fact_id`, or
  `percentage_change.from_fact_id` and `to_fact_id`. New generation requires
  these IDs. Historical responses without them remain readable through the
  legacy metric/period/unit lookup; both percentage-change IDs must be supplied
  together. All current public reports and pair edit records have been
  updated. Original model requests, responses, candidates and example-run
  snapshots remain unchanged.
- `load_agent_input(packet_path, report_path, check_clean=True)` returns only
  `evidence_packet` and `initial_report`. For paired experiments use
  `check_clean=False` for both clean and flawed cases in every architecture.
  This skips financial correctness checks while retaining schemas, evidence
  citations and fact-reference existence/parent checks. Period/value mismatches
  remain representable for experiments. It does not read private labels. Public reports now include
  deliberately flawed copies; public placement is not a correctness label.
  Reports live in `public/reports/<packet_id>/` as `clean.json` and
  `error_<index>_<type>.json`. These readable filenames never enter the returned
  model payload; the `report_id` inside each file remains opaque. Give agents
  the payload rather than file or directory access.
- One report review notebook per packet in `private/reviews/` contains checks,
  feedback, edits to a report copy, and a cell to save the final files to public.
  Original candidates and raw responses stay unchanged. There is no separate
  review JSON or required feedback file. Final copies must pass the current
  contract, which omits the confidence field.
- `private/pairs.json` stores exact before/after edits, clean/flawed IDs and paths,
  packet and pair IDs, error index, target claim, error type, expected/injected values, explanation,
  and detection/correction criteria. `create_flawed_reports.py` applies these
  edits offline; `check_flawed_reports.ipynb` shows the comparisons. These are
  lightweight pair records, not the full case/answer-key schema in section 5.
  The active error types are `direct_factual_contradiction`, `reporting_period`,
  `arithmetic`, `material_omission`, `citation_misattribution`, and
  `unsupported_inference`. Labels and answer keys must stay out of agent inputs.
  `clean_report_path` and `flawed_report_path` are relative to `public/`.
  `error_index` numbers a variant within its packet, not the claim being edited;
  `target_claim_id` identifies the changed or omitted claim, or is `null` for
  rationale-only defects. `changes[].path` gives the exact edited locations.
- Preparation uses `data/benchmark/private/` and `data/benchmark/public/`; reviewed
  releases use `data/benchmark/releases/v1/`, then `v2`, etc. Release automation and an exported JSON Schema artifact remain deferred. The testing branch implements architecture execution, confidence framing and scoring; see the current evaluation guide.

Benchmark generation shares the Analyst role and `invoke_analyst` with the architecture. The benchmark wrapper adds evidence-only generation requirements. Graph revisions use the base role plus structured output instructions.

The remainder includes the broader contract and proposals. Consult the current evaluation guide for implemented behavior and limitations.

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
error category, or an expected answer into IDs sent to the model. Descriptive
filenames are for human organization only; do not send paths to the model.
Within-case tone comparisons use `case_id`; control/error comparisons use private `pair_id`.

### Exact enum values

| Field | Allowed values |
|---|---|
| `architecture` | `baseline`, `debate`, `verification`, `hybrid` |
| `tone` | `underconfident`, `neutral`, `overconfident` |
| `content_label` — private | `unmodified`, `injected_error` |
| `defect_type` | `wrong_number`, `arithmetic`, `reporting_period`, `citation_misattribution`, `direct_factual_contradiction`, `material_omission`, `unsupported_inference` |
| verifier `status` | `PASS`, `FAIL`, `NOT_CHECKABLE` |
| revision `action` | `DEFEND`, `REVISE`, `RETRACT` |
| Trader `assessment` | `ACCEPT`, `REJECT` |
| recommendation / `investment_action` | `BUY`, `HOLD`, `SELL` |

Confidence mismatch is not a separate content defect. Risk Manager may record a
separate `calibration_concern`, without classifying it as an injected error.
`wrong_number` remains supported for older records; the active benchmark uses the six types listed above.

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
| `numeric` | `fact_id`, `metric`, `period`, `value`, `unit` | Resolve the fact and check its cited evidence, metric, period, unit and value. |
| `percentage_change` | `from_fact_id`, `to_fact_id`, `metric`, `from_period`, `to_period`, `value`, `unit` | Resolve both facts, check their metadata, then recompute `(new - old) / old * 100`; unit must be `percent`. |
| `null` | None | No supported structured factual check; reasoning remains for Risk Manager. |

Fact references are required for newly generated numerical assertions and present
in all current public reports. The parser permits them to be absent in historical
responses. An explicit unknown, uncited or mismatched fact is a check failure;
it must not silently fall back to matching another fact. Since each fact already
has an `evidence_id`, a repeated evidence/fact tuple is unnecessary. Qualitative
claims continue to cite excerpts without a `check_spec`.

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
    "from_fact_id": "EP_0012_F01",
    "to_fact_id": "EP_0012_F02",
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

Keep the original fact references for amount, arithmetic and reporting-period
errors unless the intended defect is the citation itself. A reporting-period
error can cite the source fact while asserting a different period; checking this
disagreement is part of verification. Fact references themselves are source links,
not expected answers or correctness labels.

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
  "report_path": "reports/EP_0012/error_01_arithmetic.json"
}
```

The proposed runner resolves `evidence_packet` and `initial_report`, then appends
only the `confidence_framing` sentence to the Analyst message. The report object
remains unchanged. Case IDs, paths, and tone labels are execution metadata;
agents receive the wording without these labels. The implemented loader returns
only the packet and report; framing is future work.

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
each selected pair. The current frozen six-pair selection is in `output/confidence_pairs.json`; earlier experiments used the legacy 12-pair subset.

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
- `target_claim_id`: an existing report claim ID, or `null` for a rationale error
  or an omitted claim. Explain the disputed assertion or missing evidence explicitly.
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
| `new_error_present` | Boolean or `null`; a new error appeared in the final Analyst report or Trader rationale, relative to the initial input. Applies to clean and flawed cases. |
| `new_error_explanation`, `new_error_evidence_ids` | Review explanation and supporting packet evidence IDs. A true judgement requires both; a false judgement requires an explanation. Defaults are empty for old records. |
| `scoring_provenance` | Frozen rule/rubric version, scorer/reviewer identity, reasons, and referenced audit/turn/claim IDs. |

Adjudication JSON may include `review_note`. Explicit `null` overrides an automatic label; an omitted field retains it. New-error review coverage is independent of primary defect `scoring_status`. The accepted unresolved defect rate is derived from assessment and resolution without requiring material reliance; it is reported alongside FAR. ACCEPT/REJECT concerns report support, while BUY/HOLD/SELL remains a separate investment action.

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
    reports/EP_0012/clean.json
    reports/EP_0012/error_01_arithmetic.json
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
3. Keep private answer keys and descriptive report filenames out of graph state,
   prompts, retrieval indexes, agent tools, and agent-visible logs. Agents with
   filesystem tools must not browse labelled report folders; supply the loaded
   packet and report contents instead.
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
