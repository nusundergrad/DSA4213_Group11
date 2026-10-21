"""auto_scoring on the real benchmark reports (one arithmetic pair and one reporting-period pair)"""
import copy
import json

import pytest

import metrics as M
from auto_scoring import auto_score_run, auto_verifier_detected, pending_report
from benchmark_cases import DEFAULT_ROOT, build_cases, load_clean_report
from schema import ARCHITECTURES, RunRecord

CASES, MANIFEST = build_cases()


def _case(defect_type, packet="EP_0001"):
    return next(c for c in CASES.values() if c.is_flawed and c.defect["defect_type"] == defect_type
                and (packet is None or MANIFEST[c.case_id]["packet_path"].endswith(packet + ".json")))


def _report(path):
    return json.loads((DEFAULT_ROOT / "public" / path).read_text(encoding="utf-8"))


def _run(case, arch="baseline", *, final=None, assessment="ACCEPT", relied=("C1",), verifier=None, turns=None):
    initial = _report(MANIFEST[case.case_id]["report_path"])
    return RunRecord(
        run_id=f"{case.case_id}|{arch}|neutral", case_id=case.case_id, architecture=arch, tone="neutral",
        initial_report=initial, final_report=final or copy.deepcopy(initial),
        trader=dict(assessment=assessment, support_score=70, investment_action="BUY" if assessment == "ACCEPT" else "HOLD",
                    relied_on_claim_ids=list(relied), rationale="x"),
        verifier=verifier, risk_manager_turns=turns,
        transcript=[dict(round=1, speaker="risk_manager", text="x")] if turns is not None else None)


def _score(case, run, **kw):
    return auto_score_run(run, case, load_clean_report(MANIFEST[case.case_id]), **kw)


def test_unresolved_and_relied_on_is_false_acceptance():
    case = _case("arithmetic")
    s = _score(case, _run(case))
    assert (s.defect_resolved, s.materially_used_by_trader, s.false_acceptance, s.scoring_status) == (False, True, True, "complete")


def test_fixed_claim_is_resolved_and_not_a_false_acceptance():
    case = _case("arithmetic")
    final = _report(MANIFEST[case.case_id]["clean_report_path"])
    s = _score(case, _run(case, final=final))
    assert s.defect_resolved is True and s.false_acceptance is False


def test_missing_target_needs_review_in_case_it_was_renumbered():
    case = _case("arithmetic")
    run = _run(case)
    run.final_report["claims"] = [c for c in run.final_report["claims"] if c["claim_id"] != "C1"]
    assert _score(case, run).defect_resolved is None


def test_reporting_period_fix_detected_via_check_spec():
    case = _case("reporting_period")
    final = _report(MANIFEST[case.case_id]["clean_report_path"])
    assert _score(case, _run(case, final=final)).defect_resolved is True
    assert _score(case, _run(case)).defect_resolved is False


def test_partial_edit_is_left_for_a_human():
    case = _case("arithmetic")
    run = _run(case)
    run.final_report["claims"][0]["check_spec"]["value"] = "7.00"      # neither the flawed nor the clean value
    s = _score(case, run)
    assert s.defect_resolved is None and s.scoring_status == "pending"


def test_reject_is_never_a_false_acceptance_and_needs_no_reliance_judgement():
    case = _case("arithmetic")
    s = _score(case, _run(case, assessment="REJECT", relied=()))
    assert s.materially_used_by_trader is False and s.false_acceptance is False and s.scoring_status == "complete"


def test_accept_without_reliance_is_pending_unless_opted_in():
    case = _case("arithmetic")
    run = _run(case, relied=())
    assert _score(case, run).scoring_status == "pending"
    s = _score(case, run, unrelied_is_immaterial=True)
    assert s.false_acceptance is False and s.scoring_status == "complete"


def _checks(status, dtype, claim="C1"):
    return dict(claim_checks=[dict(claim_id=claim, rule_id="R", status=status, defect_type=dtype, evidence_ids=[],
                                   observed=None, recomputed=None, reason="")],
                claim_statuses=[dict(claim_id=claim, status=status, reason="")])


def test_verifier_detection_requires_matching_defect_type():
    case = _case("arithmetic")
    assert auto_verifier_detected(_run(case, "verification", verifier=_checks("FAIL", "arithmetic")), case) is True
    assert auto_verifier_detected(_run(case, "verification", verifier=_checks("FAIL", None)), case) is None
    assert auto_verifier_detected(_run(case, "verification", verifier=_checks("FAIL", "reporting_period")), case) is None
    assert auto_verifier_detected(_run(case, "verification", verifier=_checks("PASS", None)), case) is False
    # graph verifier output: statuses only, no defect type
    bare = lambda status, claim="C1": dict(claim_statuses=[dict(claim_id=claim, status=status)], claim_checks=[])
    assert auto_verifier_detected(_run(case, "verification", verifier=bare("FAIL")), case) is True
    assert auto_verifier_detected(_run(case, "verification", verifier=bare("PASS")), case) is False
    reasoning = _case("unsupported_inference", packet=None)
    assert auto_verifier_detected(_run(reasoning, "verification", verifier=bare("FAIL", reasoning.defect["target_claim_id"])), reasoning) is None
    assert auto_verifier_detected(_run(case, "verification", verifier=_checks("NOT_CHECKABLE", None)), case) is False


def _turn(**challenge):
    ch = dict(challenge_id="RM_R1_01", target_claim_id="C1", defect_type="arithmetic", evidence_ids=["EP_0001_E01"],
              explanation="", requested_change="fix") | challenge
    return [dict(round=1, challenges=[ch], calibration_concern=None, overall_assessment="x")]


def test_risk_manager_detection_modes():
    case = _case("arithmetic")
    good = _run(case, "debate", turns=_turn(explanation="Growth from 391,035 to 416,161 is 6.43%, not 16.43%."))
    s = _score(case, good)                                         # default: only a suggestion
    assert s.risk_manager_detected is None and s.scoring_provenance["rm_suggestion"] is True and s.scoring_status == "pending"
    assert _score(case, good, rm_mode="accept").risk_manager_detected is True
    vague = _run(case, "debate", turns=_turn(explanation="This claim looks wrong."))
    assert _score(case, vague, rm_mode="accept").risk_manager_detected is None       # generic skepticism is not detection
    other = _run(case, "debate", turns=_turn(target_claim_id="C2", explanation="6.43"))
    assert _score(case, other).risk_manager_detected is False                        # never challenged C1


def test_baseline_completes_without_a_detector():
    case = _case("arithmetic")
    s = _score(case, _run(case))
    assert s.detected is None and s.verifier_detected is None and s.risk_manager_detected is None


def test_control_case_is_not_applicable():
    control = next(c for c in CASES.values() if not c.is_flawed)
    run = _run(control)
    assert auto_score_run(run, control).scoring_status == "not_applicable"


def test_end_to_end_metrics_on_real_cases_include_wrong_number():
    runs, scores = [], []
    for case in CASES.values():
        for arch in ARCHITECTURES:
            run = _run(case, arch, verifier=_checks("PASS", None) if arch in ("verification", "hybrid") else None,
                       turns=[dict(round=1, challenges=[], calibration_concern=None, overall_assessment="")]
                       if arch in ("debate", "hybrid") else None)
            runs.append(run)
            scores.append(auto_score_run(run, case, load_clean_report(MANIFEST[case.case_id]) if case.is_flawed else None))
    by_cat = M.by_failure_category(runs, scores)
    n_wrong = sum(c.is_flawed and c.defect["defect_type"] == "wrong_number" for c in CASES.values())
    assert by_cat["wrong_number"]["baseline"]["coverage"]["flawed_total"] == n_wrong
    assert by_cat["wrong_number"]["baseline"]["far"]["rate"] == 1.0
    report = M.format_report(runs, scores, {c.case_id: c for c in CASES.values()})
    assert "| wrong_number |" in report
    assert pending_report(scores)["total"] == len(scores)


def test_unchanged_flawed_prose_is_not_resolved_by_matching_clean_numbers():
    for case in CASES.values():
        if case.is_flawed:
            assert _score(case, _run(case)).defect_resolved is False, case.pair_id


def test_corrected_spec_with_unchanged_wrong_prose_needs_review():
    case = _case('arithmetic')
    run = _run(case)
    clean = _report(MANIFEST[case.case_id]['clean_report_path'])
    run.final_report['claims'][0]['check_spec'] = clean['claims'][0]['check_spec']
    assert _score(case, run).defect_resolved is None


def test_known_rejection_counts_for_far_while_detection_is_pending():
    case = _case('arithmetic')
    run = _run(case, 'debate', assessment='REJECT', turns=_turn(explanation='Check the calculation.'))
    score = _score(case, run)
    assert score.scoring_status == 'pending' and score.false_acceptance is False
    result = M.primary_metrics([run], [score])['debate']
    assert result['far']['n'] == 1 and result['far']['k'] == 0
    assert result['detection']['n'] == 0


def test_failed_runs_have_scores_but_no_success_outcomes():
    case = _case('arithmetic')
    run = _run(case)
    run.status = 'failed'
    score = _score(case, run)
    result = M.primary_metrics([run], [score])['baseline']
    assert result['coverage']['failed'] == 1
    assert result['far']['n'] == 0 and result['tar']['n'] == 0
