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
    assert score.materially_used_by_trader is None and score.scoring_status == "pending"   # C1 not in relied_on


def test_verifier_bools_become_statuses():
    rec = copy.deepcopy(RECORD)
    rec["situation"] = "situation_2"
    rec["verifier_reports"] = [{"report_id": "x", "claim_results": {"C1": False, "C2": True}}]
    run = record_to_run(rec, CASES)
    assert run.architecture == "verification" and run.risk_manager_turns is None and run.transcript is None
    assert run.verifier["claim_statuses"] == [dict(claim_id="C1", status="FAIL"), dict(claim_id="C2", status="PASS")]
    assert _score(run).verifier_detected is None          # FAIL without a defect type -> human check


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
