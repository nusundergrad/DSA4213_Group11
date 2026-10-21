# DSA4213 Agent Benchmark

A LangGraph multi-agent system that reviews financial reports, plus the benchmark and evaluation
pipeline that measures whether it catches planted errors. Start with [the current experiment workflow](docs/running-experiments.md) for commands, benchmark coverage and the supplementary challenge test.

- [1. What the pipeline does](#1-what-the-pipeline-does)
- [2. Setup](#2-setup)
- [3. API key (`.env`)](#3-api-key-env)
- [4. Check your setup](#4-check-your-setup)
- [5. Run the agents](#5-run-the-agents)
- [6. Turn run records into scores](#6-turn-run-records-into-scores)
- [7. Adjudicate what the code cannot decide](#7-adjudicate-what-the-code-cannot-decide)
- [8. Produce the findings report](#8-produce-the-findings-report)
- [9. Optional: LLM judge for debate quality](#9-optional-llm-judge-for-debate-quality)
- [10. Reading the results honestly](#10-reading-the-results-honestly)
- [11. Troubleshooting](#11-troubleshooting)
- [12. Repository map](#12-repository-map)

## 1. What the pipeline does

```text
 data/benchmark/public/            masked evidence packets + clean and flawed reports
        |  (make_run_list.py)      which report goes through which situation
        v
 output/cases_all.json
        |  (graph.run_batch)       LIVE LLM CALLS, needs OPENROUTER_API_KEY
        v
 output/<packet>/<situation>/<report>/<timestamp>.json     one record per run
        |  (graph_adapter.py)      reshape + automatic scoring, no LLM calls
        v
 eval_runs/runs.jsonl  scored.jsonl  pending.json
        |  (you fill adjudications.json, re-run the adapter)
        v
        |  (metrics.py)            no LLM calls
        v
 findings table: detection, correction, FAR, TAR, by failure category, efficiency
```

Each benchmark case is a masked 10-K evidence packet plus an Analyst report. 45 reports carry one
planted defect (the "flawed" cases); 15 are clean controls. The defect types are `wrong_number`,
`arithmetic`, `reporting_period`, `citation_misattribution`, `direct_factual_contradiction`,
`material_omission` and `unsupported_inference`.

Each report is run through one of four architectures ("situations"):

| `situation` | Architecture | What happens |
|---|---|---|
| 0 | **baseline** | The Trader judges the initial report alone: no debate, no verifier |
| 1 | **debate** | Risk Manager and Analyst argue for up to 3 rounds, then the Trader decides |
| 2 | **verification** | A rule-based verifier checks the numeric claims, then the Trader decides |
| 3 | **hybrid** | Verifier, then the debate with re-verification after each revision, then the Trader |

All conditions start from the same masked packet and report. Agent visibility follows `main`:

- **Trader** sees the current report, any verifier report and the latest agent message. It receives neither the source packet nor the whole discussion. It returns `assessment`, `support_score` (0-100), `investment_action`,
  `relied_on_claim_ids` and a rationale.
- **Risk Manager** returns structured JSON: a list of challenges (`target_claim_id`, `defect_type`,
  `explanation`, `requested_change`), an optional `calibration_concern` and an `overall_assessment`.
  The runner assigns challenge IDs (`RM_R1_01`, ...). A challenge against a claim that does not exist is
  rejected and recorded as a failed attempt. Retries require an explicit attempt budget.
- **Analyst** revisions are preserved as generated. Edits, retractions and new claim IDs are logged; the runner does not silently restore unchallenged claims. This allows new errors to remain observable.
- **Tone**: each run shows a fixed sentence beside the report ("I have low / moderate / high confidence in
  this assessment."). Every run uses the neutral sentence by default; opt in with `--tone-variants` to run the 12-pair confidence subset with the low (`underconfident`) and high (`overconfident`) sentences. The input report stays fixed; debate can subsequently revise it.
- **Usage**: exact request/response bodies and usage are saved for every attempted call, including rejected outputs. Headers and API keys are not saved. Cost stays unknown unless reported by the provider.

Headline metrics (all per architecture):

- **Detection**: the defect was identified.
- **Correction**: the defect was fixed after being detected.
- **FAR (false acceptance rate)**: the Trader ACCEPTed while the defect was unresolved *and* used it.
- **TAR (true acceptance rate)**: the Trader ACCEPTs when the input is clean. Check separately whether revisions introduced errors.
- **Control challenge rate**: first-review challenges on clean inputs. Whether each challenge is false needs adjudication.
- **Resolution**: the injected defect is absent from the final claim; this does not certify that no new error was introduced.

## 2. Setup

Requirements: Python 3.10+ and an [OpenRouter](https://openrouter.ai) account.

macOS / Linux (`py` is Windows-only and does not exist here):

```bash
python3.13 -m venv .venv      # use 3.10-3.13; see the note below if this fails
source .venv/bin/activate
pip install -r requirements.txt
```

If `python3.13` is not found, run `python3 --version` and use any 3.10-3.13 interpreter. Avoid 3.14
for now: Homebrew's 3.14 can fail at `ensurepip`, and some dependencies may not support it yet. If a
failed attempt left a broken `.venv` (no `.venv/bin/activate`), delete it first with `rm -rf .venv`.
If your prompt shows `(base)` (conda), the venv still works; just `source .venv/bin/activate`
afterwards and check `which python` points inside `.venv`.

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

All commands below are run **from the repository root** with the virtual environment active.
Use `python` on macOS/Linux, or `py` on Windows (the examples say `python`).

## 3. API key (`.env`)

The agents call models through OpenRouter. The key is read from an environment file that is
git-ignored. Steps:

1. Create a key at <https://openrouter.ai/keys>. Free models need no credit, but a key is still required.
2. Copy the template to the repository root:

   ```bash
   cp .env.template .env        # Windows: copy .env.template .env
   ```

3. Open `.env` and paste your key, with no spaces around the `=`:

   ```text
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx
   ```

Notes:

- `.env` may live at the repository root or in `src/`; both are searched. Do not put it anywhere else.
- `.env` is listed in `.gitignore`. Never commit it, paste the key into chat, or add it to the notebook.
  If a key leaks, revoke it on the OpenRouter keys page and create a new one.
- `.env` **overrides** a key already exported in your shell (the code calls `load_dotenv(override=True)`),
  so if you change keys, edit `.env`.
- Only `OPENROUTER_API_KEY` is needed to run the agents. The optional judge in section 9 needs a
  separate Anthropic key.

### Cost, free models and your budget

Free models (model IDs ending in `:free`, like the default) are **not billed**, so running the
default model cannot spend your credit. They still need a valid key. Two things to know:

- Free models are rate limited (OpenRouter documents a daily request cap that is higher once an
  account holds some purchased credit). The full run needs roughly 900+ model calls, so expect a
  free model to stop part-way and plan to run it in chunks over several days, or run only the pilot.
- If you switch `MODEL_NAME` to a paid model, the run **is billed**. To make overspending impossible,
  create a dedicated key at <https://openrouter.ai/keys> with a small **credit limit** (for example
  $2), and use that key in `.env` while testing.

### Choosing the model

The model is set by `MODEL_NAME` in `src/agent.py` (currently a free NVIDIA Nemotron model on
OpenRouter). To change it, edit that one line. The model must support JSON-object output
(`response_format={"type": "json_object"}`), because the Analyst and Trader must return JSON.
Free models are rate limited and sometimes unavailable; see [Troubleshooting](#11-troubleshooting).
Record the exact model in your report, since results depend on it.

## 4. Check your setup

**Key is loaded and looks like an OpenRouter key** (prints a verdict only, never the key):

```bash
python -c "from dotenv import dotenv_values; v=dotenv_values('.env').get('OPENROUTER_API_KEY') or ''; print('OK' if v.startswith('sk-or-') else 'WRONG: empty, or not an sk-or-... key')"
```

A real key starts with `sk-or-v1-`. A common mistake is pasting a *model name* (such as
`nvidia/nemotron-...`) into this slot, which fails with "Missing Authentication header".

**Model call works** (one tiny request):

```bash
python -c "from src.agent import get_llm; print(get_llm().invoke('Reply with OK').content)"
```

**Tests pass** (no network, no key needed):

```bash
python -m pytest tests -q
```

All offline tests should pass. If the model call fails but the key check
prints `True`, see [Troubleshooting](#11-troubleshooting).

## 5. Run the agents

This is the only step that spends API calls and time. A debate or hybrid run makes about 7 model
calls (3 Risk Manager + 3 Analyst + 1 Trader); a baseline or verification run makes 1. Each call gets one attempt by default. `--max-attempts` explicitly enables retries; failed attempts remain saved.

### 5a. One case, to see the flow

```bash
python src/graph.py \
  --packet data/benchmark/public/evidence_packets/EP_0001.json \
  --report data/benchmark/public/reports/EP_0001/error_03_arithmetic.json \
  --situation situation_1
```

This prints the routing and each agent's response but **does not save a record**. Use it for
debugging only; results come from section 5b/5c.

### 5b. A small application check

Build a case list for two packets and three architectures, then run it:

```bash
python src/evaluation/make_run_list.py --out output/cases_check.json \
  --packets EP_0001 EP_0002 --situations 0 1 3 --no-tone-variants
python -m src.graph --cases output/cases_check.json --output-root output/check_runs \
  --model nvidia/nemotron-3-ultra-550b-a55b:free --rounds 1 --reasoning-effort none --max-tokens 6000
```

That is 8 reports x 3 situations = 24 runs.

### 5c. The full run

```bash
python src/evaluation/make_run_list.py --out output/cases_all.json
python -m src.graph --cases output/cases_all.json --output-root output/full_runs \
  --model nvidia/nemotron-3-ultra-550b-a55b:free --rounds 1 --reasoning-effort none --max-tokens 6000
```

The default list has 240 neutral runs: 60 reports x 4 situations. Confidence is supplementary; add `--tone-variants` for the matched low/high subset. The subset is
chosen deterministically (`default_confidence_pairs` in `benchmark_cases.py`: round-robin over defect
types), so everyone gets the same pairs.

(`python src/graph.py` with no arguments runs `output/cases.json`, which is a one-case example.)

Details:

- Each run is written to `output/<packet>/situation_<n>/<report>/<UTC timestamp>.json`, and a failed
  case is saved too, with `"status": "failed"` and the error. Authentication/quota failures stop the batch after saving the failed attempt.
- **Resume:** `run_batch` skips a completed condition only when its input/configuration hashes match, so after an interruption
  or a rate-limit stop, run the same command again. It re-tries only the missing and failed conditions.
  Pass `skip_completed=False` to force fresh runs. Do **not** delete finished records.
- Records of non-neutral tones are written one folder deeper: `.../<report>/<tone>/<timestamp>.json`.
- A failed re-try adds another record; section 6 picks the newest one with `--keep-latest`.
- `output/` is git-ignored except for the two example case lists.
- Use `--rounds`, `--model`, `--max-tokens` and `--reasoning-effort` to configure a batch. Keep these fixed across conditions. Changed inputs or settings require a new output folder.

## 6. Turn run records into scores

The adapter reshapes the graph records into the evaluation's `RunRecord`s and scores everything it
can decide by rule. It never invents a value: anything the graph does not produce stays `pending`.

```bash
python src/evaluation/graph_adapter.py output --out eval_runs --keep-latest
```

- `--keep-latest`: when a condition (case, architecture, tone) has several records, keep the newest.
  Without it the adapter stops with an error rather than silently choosing. Note that a newer
  *failed* record replaces an older completed one, so check `runs.jsonl` for failures after a retry.
- The folder is searched recursively; `cases*.json` lists are skipped automatically.
- Failed runs have a pending score record so joins work and failure coverage remains visible; they contribute no success outcomes.

Outputs in `eval_runs/`:

| File | Contents |
|---|---|
| `runs.jsonl` | One `RunRecord` per condition (reports, Trader verdict, transcript, verifier statuses) |
| `scored.jsonl` | One `ScoredResult` per run: `complete`, `pending` or `not_applicable` |
| `pending.json` | A worksheet of the human decisions still needed, with the frozen criteria |

The command also prints pending judgements. Each metric uses its known labels from completed executions; unknown labels stay out of its denominator. A known REJECT counts as no false acceptance even if detection still needs review.

### What is decided automatically

| Field | Rule |
|---|---|
| `verifier_detected` | FAIL on the target claim. For `wrong_number`, `arithmetic` and `reporting_period` a bare FAIL counts; any other FAIL is pending; no FAIL is a miss |
| `defect_resolved` | The target claim now matches the clean text, citations and assertion: yes. A missing target needs review for renumbering or migration into the rationale. Unchanged from the flawed claim: no. Any other edit: pending |
| `materially_used_by_trader` | Trader REJECT: no. ACCEPT and the target claim is in `relied_on_claim_ids`: yes. ACCEPT without citing the target: pending (a trace of reliance is not proof) |
| `risk_manager_detected` | No challenge targets the defect claim: a miss. A challenge on the claim with the right defect type that states an expected value or period: a *suggestion* only (pending, unless `--rm-mode accept`). Any other challenge on the claim: pending |

The verifier only compares numbers in `check_spec` to the packet facts, so it **cannot** detect
citation, contradiction, omission or inference defects. Expect it to score 0 on those categories;
that is a finding, not a bug.

### Optional assumption flag

```bash
python src/evaluation/graph_adapter.py output --out eval_runs --keep-latest --unrelied-is-immaterial
```

An ACCEPT on an unresolved defect where the Trader did *not* list the target claim in
`relied_on_claim_ids` is otherwise `pending`. This flag scores those as **not** materially used, which
lowers FAR. A model may simply omit a claim it used, so state this assumption if you rely on the flag, or
adjudicate instead (next section). `--rm-mode accept` similarly trusts the automatic Risk Manager match.

## 7. Adjudicate what the code cannot decide

Open `eval_runs/pending.json`. Each entry looks like:

```json
"RUN_20261019T141121473034Z_fa358ca7_debate_neutral": {
  "architecture": "debate",
  "defect_type": "arithmetic",
  "target_claim_id": "C1",
  "detection_criterion": "Identifies that growth from 391035 to 416161 is 6.43%, not 16.43%.",
  "correction_criterion": "...",
  "materiality_criterion": "The unresolved defect is relied on to support an accepted recommendation.",
  "rm_note": "challenge on target claim but type or stated values do not clearly match the criterion",
  "fill_in": { "risk_manager_detected": null, "materially_used_by_trader": null }
}
```

For each run, read the run's transcript and Trader rationale in `runs.jsonl` (match on `run_id`) and
decide each `fill_in` field against the quoted criterion:

- `risk_manager_detected`: did the Risk Manager specifically identify *this* defect? Flagging the
  claim without identifying the planted problem is `false`.
- `defect_resolved`: is the defect fixed in the final report (per `correction_criterion`)?
- `materially_used_by_trader`: did the Trader's ACCEPT rest on the defective claim?
- `verifier_detected`: a verifier FAIL that you confirm matches the defect.

Save your answers (true/false only; leave out anything you did not decide) as `adjudications.json`:

```json
{
  "RUN_20261019T141121473034Z_fa358ca7_debate_neutral": {
    "risk_manager_detected": true,
    "materially_used_by_trader": false
  }
}
```

Then re-run the adapter with it; the file overrides the automatic value for those fields only, and
the choice is recorded in each score's `adjudicated_fields`:

```bash
python src/evaluation/graph_adapter.py output --out eval_runs --keep-latest --adjudications adjudications.json
```

Repeat until `pending` reaches 0 (or accept the stated coverage). For a defensible study, have two
people label a sample independently and report their agreement.

## 8. Produce the findings report

Build the private answer keys once (they are evaluation-only; keep them out of anything agents can read):

```bash
python src/evaluation/benchmark_cases.py --out eval_private
```

Then compute the metrics:

```bash
python src/evaluation/metrics.py \
  --cases eval_private/cases.jsonl \
  --runs eval_runs/runs.jsonl \
  --scores eval_runs/scored.jsonl --out findings.md
```

`findings.md` contains:

1. **Evaluation 1** (neutral tone): detection, correction, resolution, FAR, TAR and control challenge rate per
   architecture, with confidence intervals and the scored/total coverage.
2. **FAR by failure category**: one row per defect type.
3. **H1**: paired comparison of hybrid against each other architecture (difference with a bootstrap CI that resamples whole packets).
4. **Evaluation 2** (tone changes): support-score and decision changes between neutral and the other tones,
   for the confidence subset only; empty if you ran with `--no-tone-variants`.
5. **Efficiency**: tokens and latency per architecture. Unavailable cost is unknown, not zero.

To see the report's shape without any data, run `python src/evaluation/metrics.py --dummy`. Those
numbers are synthetic and must never be quoted as findings.

## 9. Optional: LLM judge for debate quality

`src/evaluation/judge.py` scores debate/hybrid transcripts with a model from a *different family*
than the agents, to limit self-preference bias. It is separate from the metrics above and is not
wired into a command; it needs `pip install anthropic`, `ANTHROPIC_API_KEY` in `.env`, and
`JUDGE_MODEL` set to a model ID. Smoke-test the code path offline with `python src/evaluation/judge.py`
(uses a mock judge). A judge score never replaces the answer-key scoring above. See
`judge_runs(...)` in that file for the Python API.

## 10. Reading the results honestly

- **Coverage first.** A rate computed on 3 of 45 cases is not a finding. Quote `flawed_scored/flawed_total`.
- **One model, one seed.** Temperature is 0, but a free model can still change underneath you. Name the model and the date of the run.
- **Controls are not independent.** Each clean report is shared by up to three flawed copies, so the control challenge rate rests on 15 clean reports, not 45.
- **Risk Manager detection** is automatic only for clear misses; a challenge that names the right claim but whose type or values do not clearly match stays pending for your adjudication.
- **Reliance is self-reported:** `relied_on_claim_ids` is the Trader's own claim about its reasoning, a trace rather than proof of materiality.
- **The Risk Manager is shown the defect category names** (it must label challenges), which is a mild hint that errors of those kinds may exist. State this in the report.
- **Tone** is a sentence appended beside the report; it measures sensitivity to expressed confidence, not calibrated uncertainty.
- **Failed auth runs are not data.** If a batch was run with a bad key, every record is `failed`; preserve those records and report their failures. If explicitly rerun, select attempts by a fixed rule before scoring.
- **Verifier scope.** Numeric defects only; do not read its misses on text defects as a failure of the verifier's implementation.
- **Failed runs** contribute no success outcomes; report how many there were and why (`error` in `runs.jsonl`).

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| `Missing Authentication header`, `Set OPENROUTER_API_KEY locally` or any 401 | `.env` missing, in the wrong folder, or the value is empty or not a real key (for example a model name was pasted). Re-run the check in section 4 |
| `ModuleNotFoundError` for `langgraph`, `openrouter`, `langchain_openrouter` | Activate the venv and run `pip install -r requirements.txt` |
| HTTP 429 or "quota" | Free-model rate limit. Wait and re-run only the missing cases, or switch `MODEL_NAME` |
| `model returned an empty response` / JSON parse errors or `finish_reason=length` | The model ignored the JSON instruction. The run is recorded as failed; retry later or use a stronger model |
| `Analyst changed report_id` | Model output problem; the run fails and is recorded. Retry |
| `several runs for condition ...` | Re-runs exist for that condition; add `--keep-latest` |
| `record's report_id ... does not match any case` | The record comes from a different dataset version than `data/benchmark`; rebuild records or restore the matching data |
| Many runs `pending` | Expected; see sections 6 and 7 |
| Verifier `TypeError: ... NoneType` | Fixed (units without a scale word now count as 1). If you still see it, `git pull` and rerun |

## 12. Repository map

| Path | What it is |
|---|---|
| `src/graph.py` | The four situations (0 baseline, 1 debate, 2 verification, 3 hybrid) and `run_batch` |
| `src/agent.py` | Analyst, Risk Manager and Trader agents, model name, retries |
| `src/verifier.py` | Rule-based numeric verifier |
| `src/prompts.py`, `src/state.py` | Prompts and shared graph state |
| `src/benchmark/` | Evidence packet and report creation, masking, validation |
| `src/evaluation/` | Answer keys, adapter, automatic scoring, metrics, judge |
| `data/benchmark/public/` | What the agents may see: masked packets and reports |
| `data/benchmark/private/` | Answer keys, aliases, sources (never give these to agents) |
| `docs/evaluation.md`, `docs/benchmark.md`, `docs/shared-data-contract.md` | Design and data-contract details |
| `src/justification.ipynb` | Baseline error and confidence experiments |
| `tests/` | Unit and integration tests (no network) |
