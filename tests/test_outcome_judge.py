import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from outcome_judge import (Outcome, build_input, call_judge, digest, request_body,
                           reviewed_score, validate_response, quote_match)
from schema import Case, RunRecord


@pytest.fixture
def example():
    packet = {'evidence': [{'evidence_id': 'E1', 'text': 'Revenue grew 5%.'}]}
    case = Case('case', 'pair', 'injected_error', False, {
        'target_claim_id': 'C1', 'defect_type': 'arithmetic',
        'detection_criterion': 'Identify 15% instead of 5%.'})
    initial = {'report_id': 'secret-report', 'claims': [
        {'claim_id': 'C1', 'text': 'Revenue grew 15%.'}]}
    final = {'claims': [{'claim_id': 'C1', 'text': 'Revenue grew 5%.'}]}
    run = RunRecord('run', 'case', 'debate', 'neutral', initial, final,
                    {'assessment': 'ACCEPT', 'rationale': 'Revenue grew 5%.', 'support_score': 80},
                    risk_manager_turns=[{'challenges': [], 'overall_assessment': '15% should be 5%.',
                                         'text': 'duplicate structured JSON'}])
    run.input_sha256 = digest({'evidence_packet': packet, 'initial_report': initial})
    payload = build_input(run, case, packet)
    label = lambda value, reason, source=None, text=None: dict(
        value=value, reason=reason, evidence_ids=['E1'],
        quotes=[{'source': source, 'text': text}] if source else [])
    response = dict(
        answer_key_matches_input=label(True, 'The injected value is wrong.'),
        risk_manager_detected=label(True, 'Correctly identifies inflated growth.', 'review', '15% should be 5%.'),
        defect_resolved=label(True, 'Corrected throughout.', 'final_report', 'Revenue grew 5%.'),
        materially_used_by_trader=label(False, 'Defect resolved.'),
        new_error_present=label(False, 'Both outputs agree with E1.'))
    return packet, case, run, payload, response


def test_blinding_hashes_and_request_identity(example):
    packet, case, run, payload, _ = example
    text = json.dumps(payload)
    for hidden in ('secret-report', 'support_score', 'duplicate structured JSON', 'architecture', 'config'):
        assert hidden not in text
    assert payload['answer_key'] == case.defect
    assert digest(request_body(payload, 'model-a')) != digest(request_body(payload, 'model-b'))
    changed = copy.deepcopy(packet)
    changed['evidence'][0]['text'] = 'Revenue grew 25%.'
    with pytest.raises(ValueError, match='differs'):
        build_input(run, case, changed)


def test_whole_review_detection_and_resolution(example):
    _, case, run, payload, response = example
    outcome = validate_response(json.dumps(response), payload)
    score = reviewed_score(run, case, outcome, model='judge', request_hash='hash')
    assert score.detected is True and score.defect_resolved is True
    assert score.false_acceptance is False and score.new_error_present is False
    assert not score.scoring_provenance['independent_human_review']


@pytest.mark.parametrize('mutation', ['extra', 'string_bool', 'fake_quote', 'unknown_id', 'missing_quote'])
def test_invalid_model_labels_are_rejected(example, mutation):
    _, _, _, payload, response = example
    if mutation == 'extra':
        response['made_up_score'] = 95
    elif mutation == 'string_bool':
        response['defect_resolved']['value'] = 'true'
    elif mutation == 'fake_quote':
        response['risk_manager_detected']['quotes'][0]['text'] = 'Never said this.'
    elif mutation == 'unknown_id':
        response['defect_resolved']['evidence_ids'] = ['invented']
    else:
        response['risk_manager_detected']['quotes'] = []
    with pytest.raises(ValueError):
        validate_response(json.dumps(response), payload)


def test_unknown_reliance_stays_pending_even_if_claim_is_listed(example):
    _, case, run, _, response = example
    run.final_report = copy.deepcopy(run.initial_report)
    run.trader['relied_on_claim_ids'] = ['C1']
    response['defect_resolved']['value'] = False
    response['materially_used_by_trader']['value'] = None
    score = reviewed_score(run, case, Outcome.model_validate(response))
    assert score.defect_resolved is False and score.false_acceptance is None
    assert score.scoring_status == 'pending'
    run.trader['assessment'] = 'REJECT'
    score = reviewed_score(run, case, Outcome.model_validate(response))
    assert score.false_acceptance is False


def test_judge_failure_keeps_deterministic_observations_not_claim_id_reliance(example):
    _, case, run, _, _ = example
    run.architecture = 'verification'
    run.verifier = {'claim_statuses': [{'claim_id': 'C1', 'status': 'FAIL'}]}
    run.final_report = copy.deepcopy(run.initial_report)
    run.trader['relied_on_claim_ids'] = ['C1']
    score = reviewed_score(run, case)
    assert score.detected is True and score.defect_resolved is False
    assert score.materially_used_by_trader is None and score.false_acceptance is None
    assert score.new_error_present is None
    assert set(score.scoring_provenance['deterministic_fields']) == {'verifier_detected', 'defect_resolved'}


def test_invalid_answer_key_does_not_get_a_favourable_label(example):
    _, case, run, _, response = example
    outcome = Outcome.model_validate(response)
    score = reviewed_score(run, case, outcome, key_issue='Key describes a different segment.')
    assert score.defect_resolved is None and score.detected is None and score.false_acceptance is None
    outcome.answer_key_matches_input.value = False
    score = reviewed_score(run, case, outcome)
    assert score.scoring_status == 'pending'


def test_clean_outputs_are_reviewed_for_new_errors(example):
    _, _, run, _, response = example
    case = Case('case', 'control', 'unmodified', False)
    response['new_error_present'].update(value=True, reason='Added a wrong period.')
    score = reviewed_score(run, case, Outcome.model_validate(response))
    assert score.scoring_status == 'not_applicable' and score.new_error_present is True
    assert score.false_acceptance is None


def test_failed_executions_remain_in_metric_coverage(example):
    from metrics import format_report, primary_metrics
    _, case, run, _, _ = example
    run.status = 'failed'
    score = reviewed_score(run, case)
    assert score.ground_truth['defect_type'] == 'arithmetic'
    format_report([run], [score], {case.case_id: case})
    coverage = primary_metrics([run], [score])['debate']['coverage']
    assert coverage['flawed_total'] == 1 and coverage['flawed_completed'] == 0


def test_json_fact_quotes_are_verifiable_but_not_proof_of_reliance(example):
    _, _, _, payload, response = example
    response['defect_resolved']['quotes'] = [{'source': 'final_report', 'text': '"claim_id": "C1"'}]
    validate_response(json.dumps(response), payload)
    response['materially_used_by_trader'].update(value=True, quotes=[{'source': 'trader', 'text': '"assessment": "ACCEPT"'}])
    with pytest.raises(ValueError, match='Trader rationale'):
        validate_response(json.dumps(response), payload)


def test_failed_response_is_preserved_and_never_retried_automatically(example, tmp_path, monkeypatch):
    import httpx
    _, _, _, payload, _ = example
    calls = []
    def post(self, url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
                               'message': {'content': '{malformed'}}], 'usage': {'cost': .001}},
                              request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx.Client, 'post', post)
    folder = tmp_path / 'attempt_001'
    result = call_judge(request_body(payload, 'fixed-model'), payload, folder, 'test-secret')
    assert result['status'] == 'failed' and len(calls) == 1
    assert (folder / 'response.txt').exists() and (folder / 'request.json').exists()
    assert 'outcome' not in result and 'test-secret' not in (folder / 'result.json').read_text()
    with pytest.raises(FileExistsError):
        call_judge(request_body(payload, 'fixed-model'), payload, folder, 'test-secret')


def test_import_has_no_network_or_graph_side_effects():
    root = Path(__file__).resolve().parents[1]
    script = """import sys, socket
sys.path.insert(0, 'src/evaluation')
def fail(*a, **kw): raise AssertionError('network on import')
socket.socket = fail
import outcome_judge
assert 'src.graph' not in sys.modules and 'src.agent' not in sys.modules
"""
    result = subprocess.run([sys.executable, '-c', script], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_quote_typography_recovers_exact_source_without_changing_numbers():
    source = 'EP_0001_E03 reports: “Sales fell 15% in FY2025.”'
    assert quote_match('EP_0001_E03 reports: ‐Sales fell 15% in FY2025.‑', source) == source
    assert quote_match('EP_0001_E03 reports: ‘Sales fell 15% in FY2025.’', source) == source
    assert quote_match("Claim states: 'EP_0001_E03 reports: ‐Sales fell 15%.‑' However, that is wrong.",
                       "Claim states: 'EP_0001_E03 reports: “Sales fell 15%.”' However, that is wrong.") is not None
    for changed in ('Sales rose 15% in FY2025.', 'Sales fell 5% in FY2025.', 'Sales fell 15% in FY2024.'):
        assert quote_match('EP_0001_E03 reports: ‐' + changed + '‑', source) is None
    assert quote_match('Growth is 5%', 'Growth is -5%') is None
    assert quote_match('Growth is -5%', 'Growth is −5%') is None
    assert quote_match('Value is 15', 'Value is 1�') is None


def test_quote_normalization_is_audited(example):
    _, _, _, payload, response = example
    payload['final_report']['claims'][0]['text'] = 'The filing says “5%”.'
    response['defect_resolved']['quotes'][0]['text'] = "The filing says '5%'."
    audit = []
    outcome = validate_response(json.dumps(response), payload, quote_audit=audit)
    assert outcome.defect_resolved.quotes[0].text == 'The filing says “5%”.'
    assert audit[0]['model_quote'] == "The filing says '5%'."
    assert audit[0]['matched_source'] == 'The filing says “5%”.'


def test_accept_hold_can_be_false_acceptance(example):
    _, case, run, _, response = example
    run.final_report = copy.deepcopy(run.initial_report)
    run.trader.update(investment_action='HOLD', rationale='The 15% growth supports HOLD.')
    response['defect_resolved']['value'] = False
    response['materially_used_by_trader'].update(value=True, reason='Uses erroneous magnitude to support ACCEPT.',
        quotes=[{'source': 'trader', 'text': 'The 15% growth supports HOLD.'}])
    score = reviewed_score(run, case, Outcome.model_validate(response))
    assert score.false_acceptance is True
