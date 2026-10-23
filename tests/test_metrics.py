"""Run with python test_metrics.py or python -m pytest."""
import math

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


def test_wilson_and_mcnemar():
    assert math.isclose(M.mcnemar_exact(5, 0), .0625)
    assert M.mcnemar_exact(3, 3) == 1
    assert M.rate([None, None])["rate"] is None
    lo, hi = M.wilson(0, 10)
    assert lo > -1e-12 and .25 < hi < .35


def test_paired_bootstrap_keeps_variants_from_one_packet_together():
    cases = make_cases(n_pairs=3, n_tone_pairs=0, seed=3)
    runs, scores = make_runs(cases, seed=3)
    for run in runs:
        run.initial_report['claims'] = [dict(claim_id='C1', text='Example', evidence_ids=['EP_0001_E01'])]
    compared = M.paired_comparison(runs, scores, 'hybrid', 'baseline', n_boot=100)
    assert compared['n_clusters'] == 1
    assert compared['ci'][0] == compared['ci'][1]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
