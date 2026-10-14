# Benchmark guide

We turn filing PDFs into evidence packets, mask company names, then generate
Analyst reports for the two reviewers to review.

Run the commands below from the repository root.

## What we have now

| Company | Packet | Source | Status |
|---|---|---|---|
| Apple FY2025 | `EP_0001` | `SRC_01` | Uses the Apple PDF; excerpts and spans updated |
| Microsoft FY2025 | `EP_0002` | `SRC_02` | Uses the Microsoft PDF; excerpts and spans updated |

Apple's PDF is `private/pdfs/aapl-20250927.pdf`. Its old source and packets are
backed up in `private/archive/20261012T164732Z_apple_html/`.
Microsoft's PDF is `private/pdfs/msft-20250630.pdf`. Its previous source and
packets are also backed up under `private/archive/`. Both packets now use PDFs.

Both packets are prepared. Generate Analyst candidates locally using the commands
below, then review them before publishing. No approved reports or dataset release
are included with the preparation workflow.

The report contract omits `confidence_statement`. Historical candidates that
contain this field remain readable in the review notebook but need regeneration
under the current contract before approval.

## Where files go

All paths below are inside `data/benchmark/`.

| Folder or file | What it contains |
|---|---|
| `private/pdfs/` | Original PDFs you drop here |
| `private/sources/` | Extracted text and JSON extraction details |
| `private/packets/` | Selected excerpts, numbers, and source references |
| `private/aliases.json` | Names and brands to replace with aliases |
| `private/attempts/` | Model requests, responses, and candidates |
| `private/reviews/` | Saved notebook copies with review notes |
| `private/archive/` | Backups of replaced files |
| `public/evidence_packets/` | Masked evidence for the agents |
| `public/reports/` | Reports approved by both reviewers |

**Private** files are for human review. **Public** files are for the agents.
These names do not publish anything online or restrict file access.

## 1. Add a PDF and extract its text

Save or print the filing as a PDF into `private/pdfs/`. Also keep its official
filing URL so you can add it to the private packet later.

Install the dependencies once:

```powershell
python -m pip install "pydantic>=2,<3" "python-dotenv>=1,<2" "pypdf==6.20.0" pytest
```

For a new filing, replace `your-filing.pdf` with its filename and choose a new
source ID. Apple uses `SRC_01`; Microsoft uses `SRC_02`.

```powershell
python -m src.benchmark.extract_sources your-filing.pdf --source-id SRC_03
```

This reads the local PDF and creates `private/sources/SRC_03.txt` and
`SRC_03.json`. It does not visit SEC or any other website.

Using an existing ID replaces its TXT and JSON after backing up the old files in
`private/archive/`. For example, to re-extract Microsoft:

```powershell
python -m src.benchmark.extract_sources msft-20250630.pdf --source-id SRC_02
```

Extraction does not update evidence packets or approved reports. If the text
changes, update the linked excerpts and spans, run preparation, and review them
again. Keep released datasets unchanged; work on a new copy for later versions.
If the PDF cannot be parsed, the existing source files stay unchanged.

The TXT contains the filing text. The JSON records the PDF filename, extraction
time, parser version, file hashes, and page spans. Keep the original PDF unchanged.
Scanned PDFs need OCR first; this script does not do OCR.

## 2. Make the evidence packet

This step is manual. Use `private/packets/EP_0001.json` as an example and save a
new packet with an unused ID, such as `EP_0003`.

- Record the company, fiscal year, filing URL, and source ID.
- Select exact excerpts from Items 1A and 7, including supporting and opposing evidence.
- Give each excerpt an evidence ID and a page/section reference.
- Store its `source_span` as `[start, end]` in the TXT file.
- Add numerical facts with their evidence IDs, rows, units, and fiscal periods.
  Include two consecutive periods for a comparison.
- Add company names, tickers, brands, products, and subsidiaries to `private/aliases.json`.

A span uses character positions, starting at zero. `source[start:end]` must equal
the stored excerpt; the end position is excluded. Save numbers as strings, for
example `"416161"`, with units such as `USD_million`.

## 3. Prepare the masked packet

Use your new packet ID:

```powershell
python -m src.benchmark.prepare --packet EP_0003
```

Preparation checks the source hash, excerpt matches, numbers, references, and
known identity leaks. It saves the masked packet in `public/evidence_packets/`.
It does not call a model.

Masking replaces known names with aliases and preserves numbers, dates, and units.
Reviewers still need to look for missed names. Financial figures can also make a
company recognizable.

Rerunning an unchanged packet is safe. If an existing public packet would change,
the script stops. Prepare changes in a new dataset folder using `--root <folder>`;
preserve previous versions.

## 4. Check the packet together

Open [check_evidence_packets.ipynb](../data/benchmark/check_evidence_packets.ipynb),
set `packet_id`, then restart the kernel and run all cells. The setup cell finds
the repo from any folder inside it. It prints:

- The original packet.
- The source slice and stored excerpt, with an equality check.
- The source numbers and stored values.
- The original and masked text.

The two reviewers should also open the PDF and check the right row, year, and
unit. A matching number alone does not prove that it came from the right column.
For Apple, the sales table is on **PDF page 27**, printed page 23; the selected
risk paragraphs are on **PDF page 8**, printed page 5. Microsoft's selected table
and results discussion are on **PDF page 40**; its risk excerpt is on **PDF page 17**.

Write your notes in the last Markdown cell and save a copy in `private/reviews/`.
The notebook shows private information. Its output is for reviewers, not agents.

## 5. Generate an Analyst report when ready

Keep `OPENROUTER_API_KEY` in your local environment or ignored `.env` / `src/.env`.
Choose an explicit OpenRouter model ID and use the same model for both initial reports.

```powershell
python -m src.benchmark.prepare --packet EP_0001 --generate --model "google/gemini-2.5-flash"
python -m src.benchmark.prepare --packet EP_0002 --generate --model "google/gemini-2.5-flash"
```

These commands use the model selected for the initial reports. Each makes one call at
temperature zero, using only masked evidence. There is no automatic retry or model
fallback. Requests, raw responses, usage, and failed attempts are saved privately.
Parsed candidates get a `candidate.json` in their attempt folder. The generator
also writes a `review.json` template; notebook review below replaces manually
filling in that checklist.

Reports contain BUY/SELL/HOLD, 3-5 claims, evidence IDs, and reasoning. They do
not contain a confidence field or self-assessed confidence wording. Structured
numerical assertions are checked automatically;
percentage changes allow a 0.01-percentage-point difference. Prose and ambiguous
checks still need human review.

To check a saved candidate without another model call:

```powershell
python -m src.benchmark.prepare --packet EP_0001 --report "data/benchmark/private/attempts/<attempt-id>/candidate.json"
```

## 6. Check the report in a notebook

Open [check_analyst_reports.ipynb](../data/benchmark/check_analyst_reports.ipynb).
Set `attempt_id` to the folder name printed by generation, then run all cells.
It shows the report, each claim beside its evidence, and automatic check results.
It uses the evidence saved in the original model request.

Read the output and write notes in the last Markdown cell. Both reviewers write
`approved` or `changes_requested`. Check facts, arithmetic, citations, reasoning,
counter-evidence, masking, and absence of self-assessed confidence wording. You do not need to edit
`review.json` as well.

Save a copy in `private/reviews/<report_id>.ipynb`. This keeps the report ID,
reviewer decisions, and notes together. If changes are needed, regenerate with
masked feedback using `--feedback <text-file>`; do not rewrite the candidate.

Once both reviewers approve and automatic errors are resolved, manually copy the
unchanged candidate to `public/reports/<report_id>.json`. Keep the original and
review notebook. Confirm the initial reports used the same selected model.

## 7. Add flaws to separate copies (planned)

The order for the paired benchmark is:

**Approve clean report -> copy and inject one flaw -> review the pair -> release.**

Keep the approved clean report and masked evidence unchanged. Make a separate
report with a new ID and introduce one intended defect. For example, change a
correct growth calculation to an incorrect one. If the claim has a structured
numerical assertion, change it consistently with the claim text.

Record the clean/flawed report IDs, shared pair ID, error type, changed claim,
correct answer, and explanation privately. Agents must not see these labels or
the answer key. Both reports use the same masked evidence packet.

Review that the clean report is still correct and the flawed copy contains only
the intended defect. This review confirms the injection; it does not approve the
flawed report as clean.

Flaw injection, pair storage, and evaluation loading are not implemented yet.
See [the proposed shared contract](shared-data-contract.md) for their planned
fields. The current loader is for approved clean reports and rejects numerical
errors, so it cannot serve as the paired benchmark loader unchanged.

### Confidence variants (planned)

After approving a clean report and reviewing its flawed counterpart, create
three presentations of each: low, neutral, and high expressed confidence.
Keep the report and evidence identical across these presentations. Append one
fixed sentence as Analyst text; do not regenerate or rewrite the report:

- Low: "I have low confidence in this assessment."
- Neutral: "I have moderate confidence in this assessment."
- High: "I have high confidence in this assessment."

Save the assigned tone and exact sentence in case metadata, outside the report.
Agents see the sentence as part of the Analyst's message, without the tone label
or answer key. The existing loader does not implement this yet.

Review the wording once, compare reports for equality across tones, and use the
same presentations in every architecture. A clean/flawed pair produces six
presentations. Compare acceptance of flawed reports and rejection of clean
reports across tones, using a fresh run for each presentation. This measures
sensitivity to expressed confidence, not calibrated model uncertainty. If needed,
add a no-sentence control to separate framing effects from the original report.

## 8. Save a dataset version

A clean-only dataset can be released after clean review. For the paired benchmark,
release after the flawed copies and pair records have also been reviewed.

There is no release service or approval system. Save a copy of the reviewed
`private/` and `public/` folders under `releases/v1/`, including the review notebooks.
Keep that copy unchanged once used for experiments. Later changes go into `v2`.

## Give the data to the architecture team

```python
from src.benchmark.prepare import load_agent_input

payload = load_agent_input(
    "data/benchmark/releases/v1/public/evidence_packets/EP_0001.json",
    "data/benchmark/releases/v1/public/reports/R_<approved-id>.json",
)
```

This returns `evidence_packet` and `initial_report`. Every architecture should
receive the same masked input. Keep private files and real company names out of
agent inputs. The loader assumes reports in `public/reports/` were approved.
The existing debate graph is not connected to this workflow yet.

## Which Analyst do we use?

The benchmark and demo use `invoke_analyst` in `src/agent.py` with the existing
`ChatOpenRouter` client. `src/prompts.py` keeps the original Analyst prompt and
adds masked-evidence and JSON-output instructions for benchmark generation.
Preparation still validates reports and saves exact requests, raw responses,
candidates, and review files privately.

The benchmark requires an explicit model, temperature 0, no retries, and no
provider fallback. The demo keeps its ticker, mock filing, conversation history,
text output, and `openrouter/free` model. Importing the shared agent does not load
credentials or create a model client; the demo client is created on first use.

Graph routing, graph state, and Risk Manager and Trader prompts are unchanged. Connecting the graph to masked evidence and saved initial reports
is separate architecture work. Experiments should start from the same saved
report, including its intended flaw when applicable.

## Reproduce or test the work

To repeat an extraction, copy the same PDF into a separate folder's
`private/pdfs/`, then run extraction with `--root <folder>`. Use the recorded parser
version and compare the PDF and text hashes. Timestamps will differ.

Generation and the shared Analyst tests use the project dependencies.
Install them and run the offline checks with:

```powershell
python -m pip install -r requirements.txt
python -m pytest tests -q
```

These checks help prepare the benchmark. They are not the experimental verifier
or a substitute for the two reviewers' review.
