import json
from langchain_core.messages import AIMessage

from src import agent, prompts
from src.benchmark.prepare import ROOT
from challenge_experiment import run_experiment, transition_metrics


def test_challenge_branches_share_fixed_evidence_report_and_initial_response(tmp_path, monkeypatch):
    seen = []

    class Fake:
        def invoke(self, messages, **kwargs):
            seen.append(messages)
            challenged = any("don't think" in m.content for m in messages)
            return AIMessage(content=json.dumps({'assessment': 'REJECT' if challenged else 'ACCEPT',
                'challenges': [], 'calibration_concern': None, 'overall_assessment': 'Example review.'}))

    monkeypatch.setattr(agent, 'get_llm', lambda: Fake())
    args = (ROOT / 'public/evidence_packets/EP_0001.json', ROOT / 'public/reports/EP_0001/clean.json', tmp_path)
    result = run_experiment(*args, model='fake-test-model', live=True)
    assert len(seen) == 5
    assert all(prompts.NUMERICAL_PRECISION_INSTRUCTIONS in turn[0].content for turn in seen)
    assert all(turn[1].content == seen[0][1].content for turn in seen)
    assert seen[1][2].content == seen[3][2].content
    assert result['branches']['disagreement']['verdict_changed']
    assert not result['branches']['neutral']['verdict_changed']
    assert transition_metrics(list(result['branches'].values()))['pending'] == 2
    monkeypatch.setattr(agent, 'get_llm', lambda: (_ for _ in ()).throw(AssertionError('network')))
    assert run_experiment(*args, model='fake-test-model', live=False) == result


def test_correctness_transitions_require_adjudication_not_just_a_flip():
    result = transition_metrics([
        {'initial_assessment_correct': False, 'final_assessment_correct': True},
        {'initial_assessment_correct': True, 'final_assessment_correct': False},
        {'initial_assessment_correct': True, 'final_assessment_correct': True},
        {'initial_assessment_correct': None, 'final_assessment_correct': None}])
    assert result['useful_correction'] == {'k': 1, 'n': 1}
    assert result['incorrect_reversal'] == {'k': 1, 'n': 2}
    assert result['pending'] == 1


def test_malformed_response_is_preserved_without_inventing_a_verdict(tmp_path, monkeypatch):
    class Fake:
        def invoke(self, messages, **kwargs):
            return AIMessage(content='{}')

    monkeypatch.setattr(agent, 'get_llm', lambda: Fake())
    result = run_experiment(ROOT / 'public/evidence_packets/EP_0001.json',
                            ROOT / 'public/reports/EP_0001/clean.json', tmp_path,
                            model='fake-test-model', live=True)
    assert result['status'] == 'incomplete' and result['initial_assessment'] is None
    assert all(b['verdict_changed'] is None for b in result['branches'].values())
    saved = json.loads((tmp_path / 'initial.json').read_text(encoding='utf-8'))
    assert saved['status'] == 'failed' and saved['model_calls'][0]['response']['content'] == '{}'
