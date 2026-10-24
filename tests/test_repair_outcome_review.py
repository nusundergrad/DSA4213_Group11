import copy
import json
from types import SimpleNamespace

import pytest

from outcome_judge import quote_match, request_body
from repair_outcome_review import apply_corrections, budget_allows, needs_reliance, reserve_cost, correct_saved_quote
from schema import Case


@pytest.mark.parametrize('previous_label', [True, False, None])
def test_selection_does_not_depend_on_previous_reliance_label(previous_label):
    run = SimpleNamespace(status='completed', trader={'assessment': 'ACCEPT', 'investment_action': 'HOLD'},
                          initial_report={'text': 'Wrong'}, final_report={'text': 'Wrong'})
    case = SimpleNamespace(is_flawed=True)
    outcome = SimpleNamespace(answer_key_matches_input=SimpleNamespace(value=True),
                              defect_resolved=SimpleNamespace(value=False),
                              materially_used_by_trader=SimpleNamespace(value=previous_label))
    assert needs_reliance(run, case, outcome)
    run.trader['assessment'] = 'REJECT'
    assert not needs_reliance(run, case, outcome)
    run.trader['assessment'] = 'ACCEPT'
    run.final_report = {'text': 'Corrected'}
    outcome.defect_resolved.value = True
    assert not needs_reliance(run, case, outcome)


def test_budget_reserves_inflight_calls_and_existing_usage():
    assert budget_allows(.1, .2, 3.32, 3.22, 2, 10)
    assert not budget_allows(1.9, .2, 5.12, 3.22, 2, 10)
    assert not budget_allows(.1, .2, 9.9, 3.22, 2, 10)
    # If billing is delayed, local charges still count toward the total.
    assert not budget_allows(1.8, .3, 8, 8, 3, 10)
    assert reserve_cost({'messages': ['x' * 1000], 'max_tokens': 1000}) > .0035


def test_annotation_correction_is_guarded_and_evidence_backed():
    from pathlib import Path
    from benchmark_cases import build_cases, DEFAULT_ROOT
    root = Path(__file__).resolve().parents[1]
    correction = json.loads((root / 'data/benchmark/private/annotation_corrections.json').read_text(encoding='utf-8'))['corrections'][0]
    cid = correction['case_id']
    frozen = {cid: Case(cid, 'pair', 'injected_error', False, copy.deepcopy(correction['previous_defect']))}
    assert apply_corrections(frozen, [correction]) == {cid}
    current, _ = build_cases()
    assert frozen[cid].defect == current[cid].defect
    with pytest.raises(ValueError, match='frozen'):
        apply_corrections(frozen, [correction])
    packet = json.loads((DEFAULT_ROOT / 'public/evidence_packets/EP_0008.json').read_text(encoding='utf-8'))
    quote = correction['corrected_defect']['expected']['source_quotes'][0]
    text = next(e['text'] for e in packet['evidence'] if e['evidence_id'] == quote['evidence_id'])
    assert quote_match(quote['quote'], text) is not None


def test_reliance_request_has_one_label_and_explicit_hold_rule():
    payload = {'evidence': {'evidence': [{'evidence_id': 'E1'}]}}
    body = request_body(payload, 'fixed-model', 'reliance')
    assert list(body['response_format']['json_schema']['schema']['properties']) == ['materially_used_by_trader']
    assert 'HOLD is never a reason to abstain' in body['messages'][0]['content']
    assert 'hypothetical corrected report' in body['messages'][0]['content']
    assert 'Reviewer feedback or prior detection is NOT required' in body['messages'][0]['content']
    assert 'risk_manager_detected:' not in body['messages'][0]['content']
    assert 'answer_key_matches_input:' not in body['messages'][0]['content']


def test_manual_quote_fix_preserves_labels_and_rejects_stale_correction():
    response = {'answer_key_matches_input': {'value': True, 'reason': 'Matches the periods.',
                'quotes': [{'source': 'evidence', 'text': 'Joined table rows'}], 'evidence_ids': ['E1']}}
    patch = {'field': 'answer_key_matches_input', 'quote_index': 0, 'source': 'evidence',
             'original_quote': 'Joined table rows', 'replacement_quote': 'Exact table'}
    fixed = json.loads(correct_saved_quote(json.dumps(response), patch))
    assert fixed['answer_key_matches_input']['value'] is True
    assert fixed['answer_key_matches_input']['reason'] == response['answer_key_matches_input']['reason']
    assert fixed['answer_key_matches_input']['quotes'][0]['text'] == 'Exact table'
    with pytest.raises(ValueError, match='saved response'):
        correct_saved_quote(json.dumps(fixed), patch)
