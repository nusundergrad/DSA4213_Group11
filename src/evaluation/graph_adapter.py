"""Convert records written by ``src/graph.py::run_batch`` into evaluation ``RunRecord``s.

The graph record has no private labels. This adapter only reshapes what it contains and never
invents a value: a field the graph does not produce stays ``None`` (or ``{}``), so the affected
score is ``pending`` instead of silently wrong.

    graph record                         RunRecord
    situation_1 / _2 / _3           ->   architecture debate / verification / hybrid
    initial_report.report_id        ->   case_id (via benchmark_cases.case_id_for)
    initial_report, final_reports[-1] -> initial_report, final_report
    trader_verdict                  ->   trader (support_score and relied_on_claim_ids only if present)
    messages                        ->   transcript (+ unstructured risk_manager_turns)
    verifier_reports[0].claim_results -> verifier.claim_statuses (PASS / FAIL / NOT_CHECKABLE)

Not available from the graph today, so left empty: tone (defaults to neutral), support_score,
relied_on_claim_ids, structured Risk Manager challenges, claim_checks (the type of a verifier
FAIL) and usage. See docs/evaluation.md.

CLI:
    python src/evaluation/graph_adapter.py output/ --out outputs/eval_runs
"""
from __future__ import annotations

import json
from pathlib import Path

from schema import RunRecord, write_jsonl
from benchmark_cases import build_cases, case_id_for, load_clean_report

SITUATION_TO_ARCHITECTURE = {
    "situation_0": "baseline", "baseline": "baseline",
    "situation_1": "debate", "debate": "debate",
    "situation_2": "verification", "verification": "verification",
    "situation_3": "hybrid", "hybrid": "hybrid",
}
SPEAKERS = {"analyst_agent": "analyst", "risk_manager_agent": "risk_manager"}
RM_FIELDS = {"challenge_id", "target_claim_id", "defect_type", "explanation"}


def architecture_for(situation: str) -> str:
    try:
        return SITUATION_TO_ARCHITECTURE[situation]
    except KeyError:
        raise ValueError(f"unknown situation {situation!r}; known: {sorted(SITUATION_TO_ARCHITECTURE)}") from None


def build_transcript(messages: list) -> list:
    """Role-labelled turns. A round starts at each Risk Manager message; the Analyst reply that
    follows belongs to the same round. Human/system/trader messages are not part of the debate."""
    out, round_no = [], 0
    for m in messages:
        speaker = SPEAKERS.get(m.get("name"))
        if speaker is None:
            continue
        if speaker == "risk_manager":
            round_no += 1
        out.append(dict(round=max(round_no, 1), speaker=speaker, text=m.get("content") or ""))
    return out


def build_risk_manager_turns(record: dict, transcript: list):
    """Structured challenges if the graph supplies them, else unstructured turns.

    An unstructured turn has ``challenges: None`` (NOT an empty list: an empty list would mean
    'the Risk Manager challenged nothing', which scoring would count as a miss)."""
    structured = record.get("risk_manager_turns")
    if structured is not None:
        return structured
    turns = [dict(round=t["round"], challenges=None, structured=False, text=t["text"])
             for t in transcript if t["speaker"] == "risk_manager"]
    return turns or None


def build_verifier(record: dict):
    """Statuses for the first verifier pass, which runs on the frozen initial report. (The Analyst
    keeps the same report_id across revisions, so report_id cannot tell passes apart.)"""
    reports = record.get("verifier_reports") or []
    if not reports:
        return None
    statuses = []
    for claim_id, result in (reports[0].get("claim_results") or {}).items():
        if result is True:
            status = "PASS"
        elif result is False:
            status = "FAIL"
        else:
            status = str(result).upper() if result else "NOT_CHECKABLE"
        statuses.append(dict(claim_id=claim_id, status=status))
    return dict(claim_statuses=statuses, claim_checks=reports[0].get("claim_checks", []),
                n_passes=len(reports))


def build_trader(record: dict) -> dict:
    verdict = record.get("trader_verdict") or {}
    trader = {k: verdict.get(k) for k in ("assessment", "investment_action", "rationale")}
    for optional in ("support_score", "relied_on_claim_ids"):
        if verdict.get(optional) is not None:
            trader[optional] = verdict[optional]
    trader.setdefault("support_score", None)
    return trader


def record_to_run(record: dict, cases: dict, *, tone: str = "neutral") -> RunRecord:
    initial = record.get("initial_report") or {}
    report_id = initial.get("report_id")
    case_id = case_id_for(report_id) if report_id else None
    if case_id not in cases:
        raise ValueError(f"record's report_id {report_id!r} does not match any case in the answer keys")
    architecture = architecture_for(record["situation"])
    finals = record.get("final_reports") or [initial]
    transcript = build_transcript(record.get("messages") or [])
    has_debate = architecture in ("debate", "hybrid")
    completed = record.get("status") == "completed"
    stamp = record.get("run_timestamp", "unknown")
    return RunRecord(
        run_id=f"RUN_{stamp}_{case_id.removeprefix('CASE_')[:8]}_{architecture}_{tone}",
        case_id=case_id, architecture=architecture, tone=tone,
        initial_report=initial, final_report=finals[-1],
        trader=build_trader(record),
        verifier=build_verifier(record) if architecture in ("verification", "hybrid") else None,
        risk_manager_turns=build_risk_manager_turns(record, transcript) if has_debate else None,
        analyst_revision_turns=[t for t in transcript if t["speaker"] == "analyst"] if has_debate else None,
        transcript=transcript if has_debate else None,
        usage=record.get("usage") or {},
        status="completed" if completed else "failed",
        error=None if completed else {"message": record.get("error")},
        started_at=stamp, config=dict(situation=record["situation"], debate_rounds=record.get("debate_round")),
    )


def load_records(source) -> list:
    """A record file, or a folder searched recursively for run_batch output (*.json)."""
    source = Path(source)
    files = [source] if source.is_file() else sorted(source.rglob("*.json"))
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def adapt_all(records: list, cases: dict, *, tone: str = "neutral", keep: str = "error") -> list:
    """keep: 'error' rejects several runs of one condition (metrics.py does too); 'latest' keeps the newest."""
    chosen = {}
    for rec in records:
        run = record_to_run(rec, cases, tone=tone)
        key = (run.case_id, run.architecture, run.tone)
        if key in chosen:
            if keep != "latest":
                raise ValueError(f"several runs for condition {key}; pass keep='latest' to take the newest")
            if run.started_at < chosen[key].started_at:
                continue
        chosen[key] = run
    return list(chosen.values())


if __name__ == "__main__":
    import argparse
    from auto_scoring import auto_score_run, pending_report
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="a run_batch record file, or the output folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tone", default="neutral")
    ap.add_argument("--keep-latest", action="store_true")
    args = ap.parse_args()
    cases, manifest = build_cases()
    runs = adapt_all(load_records(args.source), cases, tone=args.tone, keep="latest" if args.keep_latest else "error")
    scores = [auto_score_run(r, cases[r.case_id], load_clean_report(manifest[r.case_id]))
              for r in runs if r.status == "completed"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "runs.jsonl", runs)
    write_jsonl(out / "scored.jsonl", scores)
    print(f"{len(runs)} runs, {len(scores)} scored -> {out}")
    print(pending_report(scores))
