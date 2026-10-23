"""graph.py run_batch records -> RunRecord -> auto scoring (real sample: debate on EP_0001 arithmetic)"""
import copy
import json
from pathlib import Path

import pytest

import metrics as M
from auto_scoring import auto_score_run
from benchmark_cases import build_cases, load_clean_report
from graph_adapter import adapt_all, architecture_for, record_to_run

CASES, MANIFEST = build_cases()
FIXTURE = Path(__file__).parent / "fixtures" / "graph_record_debate_arithmetic.json"
RECORD = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _score(run, **kw):
    return auto_score_run(run, CASES[run.case_id], load_clean_report(MANIFEST[run.case_id]), **kw)


def test_maps_to_the_right_case_and_architecture():
    run = record_to_run(RECORD, CASES)
    case = CASES[run.case_id]
    assert case.is_flawed and case.defect["defect_type"] == "arithmetic"
    assert run.architecture == "debate" and run.tone == "neutral" and run.status == "completed"
    assert run.initial_report["claims"][0]["text"] != run.final_report["claims"][0]["text"]
    assert run.trader["assessment"] == "ACCEPT" and run.trader["investment_action"] == "HOLD"
    assert run.verifier is None


def test_cli_preserves_explicit_null_and_exports_output_review(tmp_path):
    import subprocess
    import sys
    rec = copy.deepcopy(RECORD)
    rec['final_reports'] = [rec['initial_report']]
    rec['trader_verdict']['relied_on_claim_ids'] = ['C1']
    source = tmp_path / 'record.json'
    source.write_text(json.dumps(rec), encoding='utf-8')
    run = record_to_run(rec, CASES)
    review = tmp_path / 'review.json'
    review.write_text(json.dumps({run.run_id: {'materially_used_by_trader': None,
        'review_note': 'The cited claim includes more than its defective value.'}}), encoding='utf-8')
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / 'evaluation'
    subprocess.run([sys.executable, str(root / 'src/evaluation/graph_adapter.py'), str(source),
                    '--out', str(out), '--adjudications', str(review), '--confidence-pairs',
                    str(root / 'output/confidence_pairs.json')], check=True, capture_output=True, text=True)
    score = json.loads((out / 'scored.jsonl').read_text(encoding='utf-8'))
    assert score['materially_used_by_trader'] is None and score['false_acceptance'] is None
    assert score['scoring_provenance']['review_note']
    worksheet = json.loads((out / 'output_review.json').read_text(encoding='utf-8'))
    assert worksheet[run.run_id]['new_error_present'] is None
    cases = [json.loads(line) for line in (out / 'cases.jsonl').read_text(encoding='utf-8').splitlines()]
    assert sum(c['confidence_subset'] for c in cases) == 12


def test_transcript_rounds_and_roles():
    run = record_to_run(RECORD, CASES)
    assert [(t["round"], t["speaker"]) for t in run.transcript] == [
        (1, "risk_manager"), (1, "analyst"), (2, "risk_manager"), (2, "analyst"), (3, "risk_manager"), (3, "analyst")]


def test_missing_graph_fields_are_not_invented():
    run = record_to_run(RECORD, CASES)
    assert run.trader["support_score"] is None and "relied_on_claim_ids" not in run.trader
    assert all(t["challenges"] is None for t in run.risk_manager_turns)   # unstructured, NOT an empty list
    assert run.usage == {}


def test_unstructured_risk_manager_is_pending_not_a_miss():
    score = _score(record_to_run(RECORD, CASES))
    assert score.defect_resolved is True                  # Analyst restored C1 to the clean claim
    assert score.risk_manager_detected is None            # must not be False although the RM caught it
    assert score.scoring_status == "pending"
    assert "mentions target claim and an expected value: True" in score.scoring_provenance["rm_note"]


def test_structured_fields_complete_the_score():
    rec = copy.deepcopy(RECORD)
    rec["trader_verdict"].update(support_score=60, relied_on_claim_ids=["C2"])
    rec["risk_manager_turns"] = [dict(round=1, challenges=[dict(
        challenge_id="X1", target_claim_id="C1", defect_type="arithmetic",
        explanation="C1 growth is 16.43% but the facts give 6.43%")])]
    score = _score(record_to_run(rec, CASES), rm_mode="accept")
    assert score.risk_manager_detected is True and score.detected is True
    assert score.defect_resolved is True
    # defect was resolved, so reliance need not be adjudicated and the score completes
    assert score.scoring_status == "complete" and score.false_acceptance is False


def test_verifier_bools_become_statuses():
    rec = copy.deepcopy(RECORD)
    rec["situation"] = "situation_2"
    rec["verifier_reports"] = [{"report_id": "x", "claim_results": {"C1": False, "C2": True}}]
    run = record_to_run(rec, CASES)
    assert run.architecture == "verification" and run.risk_manager_turns is None and run.transcript is None
    assert run.verifier["claim_statuses"] == [dict(claim_id="C1", status="FAIL"), dict(claim_id="C2", status="PASS")]
    assert _score(run).verifier_detected is True          # numeric defect: bare FAIL on the target counts


def test_failed_record_is_kept_but_marked_failed():
    rec = copy.deepcopy(RECORD)
    rec.update(status="failed", error="boom")
    assert record_to_run(rec, CASES).status == "failed"


def test_unknown_report_or_situation_is_rejected():
    rec = copy.deepcopy(RECORD)
    rec["initial_report"]["report_id"] = "R_unknown"
    with pytest.raises(ValueError):
        record_to_run(rec, CASES)
    with pytest.raises(ValueError):
        architecture_for("situation_9")


def test_duplicates_rejected_unless_latest():
    other = copy.deepcopy(RECORD)
    other["run_timestamp"] = "99999999T000000000000Z"
    with pytest.raises(ValueError):
        adapt_all([RECORD, other], CASES)
    runs = adapt_all([RECORD, other], CASES, keep="latest")
    assert len(runs) == 1 and runs[0].started_at == other["run_timestamp"]


def test_unstructured_runs_do_not_enter_false_challenge_rate():
    rec = copy.deepcopy(RECORD)
    clean_id = next(c for c in CASES.values() if not c.is_flawed and c.case_id != record_to_run(RECORD, CASES).case_id)
    rec["initial_report"]["report_id"] = "R_" + clean_id.case_id.removeprefix("CASE_")
    run = record_to_run(rec, CASES)
    score = auto_score_run(run, CASES[run.case_id])
    m = M.primary_metrics([run], [score], architectures=("debate",))["debate"]
    assert m["false_challenge"]["n"] == 0


def test_failed_record_without_initial_report_is_recovered_from_report_path():
    rec = {k: v for k, v in RECORD.items() if k not in ("initial_report", "final_reports")}
    rec.update(status="failed", error="boom", report_path=str(next(
        Path(__file__).parents[1].joinpath("data/benchmark/public/reports/EP_0001").glob("error_03_arithmetic.json"))))
    run = record_to_run(rec, CASES)
    assert run.status == "failed" and run.case_id == record_to_run(RECORD, CASES).case_id


def test_load_records_skips_case_lists_in_the_output_folder(tmp_path):
    from graph_adapter import load_records
    (tmp_path / "cases.json").write_text('[{"evidence_packet": "EP_0001", "report": "x", "situation": 1}]')
    (tmp_path / "run.json").write_text(json.dumps(RECORD))
    assert len(load_records(tmp_path)) == 1


def test_adjudication_completes_a_pending_run_and_worksheet_lists_the_gap():
    from auto_scoring import pending_worksheet
    run = record_to_run(RECORD, CASES)
    sc = _score(run)
    assert sc.scoring_status == "pending"
    need = pending_worksheet([run], [sc], CASES)[run.run_id]["fill_in"]
    assert set(need) == {"risk_manager_detected", "materially_used_by_trader"} and "defect_resolved" not in need
    done = _score(run, adjudication=dict(risk_manager_detected=False, materially_used_by_trader=True))
    assert done.scoring_status == "complete" and done.defect_resolved is True and done.false_acceptance is False
    with pytest.raises(ValueError, match="unknown adjudication"):
        _score(run, adjudication=dict(bogus=True))
