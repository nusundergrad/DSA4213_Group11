"""Run with python test_metrics.py or python -m pytest."""
import math
import copy
import pytest

import metrics as M
from dummy_data import make_cases, make_runs, PLANTED, OBJECTIVE_DEFECTS
from schema import RunRecord, Case
from scoring import score_run


def test_planted_rates_and_counts():
    cases = make_cases(n_pairs=2000, n_tone_pairs=10, seed=1)
    runs, scores = make_runs(cases, seed=1)
    result = M.primary_metrics(runs, scores)
    for arch, p in PLANTED.items():
        assert abs(result[arch]["tar"]["rate"] - p["acc_clean"]) < .04
        assert result[arch]["coverage"]["flawed_scored"] == 2000
    assert result["baseline"]["detection"]["rate"] is None
    assert result["verification"]["correction"]["rate"] is None
    assert result["hybrid"]["far"]["rate"] < result["baseline"]["far"]["rate"]


def test_tone_and_pairing():
    cases = make_cases(n_pairs=500, n_tone_pairs=500, seed=2)
    runs, scores = make_runs(cases, seed=2)
    tone = M.tone_metrics(runs, scores, cases)
    assert tone["baseline"]["overconfident"]["sensitivity_mean"] > 0
    assert tone["baseline"]["underconfident"]["sensitivity_mean"] < 0
    assert tone["baseline"]["overconfident"]["dD"] is None
    paired = M.paired_comparison(runs, scores, "hybrid", "baseline")
    assert paired["diff"] < 0 and paired["p_mcnemar"] < .001


def test_materiality_and_pending():
    case = Case("CASE_1", "PAIR_1", "injected_error", False,
                dict(target_claim_id="C1", defect_type="arithmetic"))
    report = dict(recommendation="BUY", claims=[dict(claim_id="C1", text="bad", evidence_ids=[])])
    trader = dict(assessment="ACCEPT", support_score=75, investment_action="BUY")
    run = RunRecord("run", case.case_id, "baseline", "neutral", report, report, trader)
    pending = score_run(run, case, defect_resolved=False)
    assert pending.scoring_status == "pending" and pending.false_acceptance is None
    scored = score_run(run, case, defect_resolved=False, materially_used_by_trader=False)
    assert scored.scoring_status == "complete" and scored.false_acceptance is False
    scored = score_run(run, case, defect_resolved=False, materially_used_by_trader=True)
    assert scored.false_acceptance is True
    assert M.primary_metrics([run], [pending])["baseline"]["coverage"]["flawed_scored"] == 0
    metrics = M.primary_metrics([run], [pending])['baseline']
    assert metrics['accepted_unresolved']['rate'] == 1
    assert metrics['far']['n'] == 0
    assert metrics['investment_actions'] == {'BUY': 1, 'HOLD': 0, 'SELL': 0}


@pytest.mark.parametrize('assessment,resolved,expected', [
    ('ACCEPT', False, True), ('ACCEPT', True, False), ('ACCEPT', None, None),
    ('REJECT', False, False), ('REJECT', True, False), ('REJECT', None, False)])
def test_accepted_unresolved(assessment, resolved, expected):
    from types import SimpleNamespace
    assert M.accepted_unresolved(SimpleNamespace(trader={'assessment': assessment}),
                                 SimpleNamespace(defect_resolved=resolved)) is expected


def test_new_error_rate_uses_reviewed_completed_outputs_only():
    cases = make_cases(n_pairs=3, n_tone_pairs=0)
    runs, scores = make_runs(cases)
    pairs = [(r, s) for r, s in zip(runs, scores) if r.architecture == 'baseline']
    pairs[0][1].new_error_present = True
    pairs[1][1].new_error_present = False
    pairs[2][0].status = 'failed'
    pairs[2][1].new_error_present = True
    m = M.primary_metrics(runs, scores)['baseline']
    assert m['new_error']['k'] == 1 and m['new_error']['n'] == 2
    assert m['coverage']['output_reviewed'] == 2
    assert m['coverage']['output_total'] == len(pairs) - 1


def test_wilson_and_mcnemar():
    assert math.isclose(M.mcnemar_exact(5, 0), .0625)
    assert M.mcnemar_exact(3, 3) == 1
    assert M.rate([None, None])["rate"] is None
    lo, hi = M.wilson(0, 10)
    assert lo > -1e-12 and .25 < hi < .35


def test_detection_coverage_separates_pending_and_failed_cases():
    cases = make_cases(n_pairs=4, n_tone_pairs=0)
    runs, scores = make_runs(cases)
    rows = [(r, s) for r, s in zip(runs, scores)
            if r.architecture == 'debate' and cases[r.case_id].is_flawed]
    for (_, score), detected in zip(rows, [True, False, None, True]):
        score.detected = detected
        score.scoring_status = 'pending'
    rows[-1][0].status = 'failed'
    m = M.primary_metrics(runs, scores)['debate']
    assert m['detection']['k'] == 1 and m['detection']['n'] == 2
    assert m['coverage']['flawed_completed'] == 3
    assert m['coverage']['detection_pending'] == 1
    report = M.format_report(runs, scores, cases)
    assert '| debate | 4 | 3 | 1 | 1 | 1 | 1 |' in report
    assert 'Detection uses detected / (detected + missed)' in report


def test_paired_bootstrap_keeps_variants_from_one_packet_together():
    cases = make_cases(n_pairs=3, n_tone_pairs=0, seed=3)
    runs, scores = make_runs(cases, seed=3)
    for run in runs:
        run.initial_report['claims'] = [dict(claim_id='C1', text='Example', evidence_ids=['EP_0001_E01'])]
    compared = M.paired_comparison(runs, scores, 'hybrid', 'baseline', n_boot=100)
    assert compared['n_clusters'] == 1
    assert compared['ci'] is None
    assert 'packet-bootstrap CI not estimated: one packet' in M.format_report(runs, scores, cases)


def test_neutral_repeats_measure_variation_without_replacing_original():
    cases = make_cases(n_pairs=1, n_tone_pairs=0)
    runs, scores = make_runs(cases)
    repeated, repeated_scores = copy.deepcopy((runs, scores))
    for r, s in zip(repeated, repeated_scores):
        r.run_id += '_repeat'
        s.run_id = r.run_id
    repeated[0].trader['assessment'] = 'REJECT' if runs[0].trader['assessment'] == 'ACCEPT' else 'ACCEPT'
    repeated[0].trader['support_score'] = None
    result = M.neutral_repeat_metrics(runs, scores, repeated, repeated_scores)
    m = result[repeated[0].architecture]
    assert m['flip']['k'] == 1 and m['support_n'] == m['n'] - 1
    with pytest.raises(ValueError, match='independent executions'):
        M.neutral_repeat_metrics(runs, scores, runs, scores)
    repeated[0].initial_report = {'changed': True}
    with pytest.raises(ValueError, match='identical inputs'):
        M.neutral_repeat_metrics(runs, scores, repeated, repeated_scores)


def test_neutral_repeats_reject_different_settings():
    cases = make_cases(n_pairs=1, n_tone_pairs=0)
    runs, scores = make_runs(cases)
    repeated, repeated_scores = copy.deepcopy((runs, scores))
    runs[0].config['model'] = 'original'
    repeated[0].config['model'] = 'changed'
    with pytest.raises(ValueError, match='mixed model'):
        M.neutral_repeat_metrics(runs, scores, repeated, repeated_scores)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
