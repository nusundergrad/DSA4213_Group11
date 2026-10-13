"""Run: python test_judge.py   (or: python -m pytest)"""
import json
import os
import tempfile

import judge as J
from dummy_data import make_cases, make_runs


def _runs():
    cs = make_cases(n_pairs=20, n_tone_pairs=6)
    runs, _ = make_runs(cs)
    return cs, [r for r in runs if r.architecture in ("debate", "hybrid")]


def test_prompt_is_blind():
    _, rs = _runs()
    for r in rs[:10]:
        p = J.build_prompt(r, "EVIDENCE", 0).lower()
        for leak in ("hybrid", "debate", "flawed", "clean", "risk_manager", "overconfident", "underconfident"):
            assert leak not in p, leak
        assert "participant a" in p


def test_mapping_is_deterministic_and_varies():
    _, rs = _runs()
    assert J.build_prompt(rs[0], "E", 0) == J.build_prompt(rs[0], "E", 0)
    assert any(J.build_prompt(r, "E", 0) != J.build_prompt(r, "E", 1) for r in rs)


def test_parse_and_validation():
    ok = json.dumps({k: {"score": 3, "evidence": "q"} for k in J.DIMENSIONS})
    assert set(J.parse_scores("```json\n" + ok + "\n```").values()) == {3}
    bad = json.dumps({k: {"score": 9, "evidence": "q"} for k in J.DIMENSIONS})
    try:
        J.parse_scores(bad)
        assert False, "should reject out-of-range score"
    except ValueError:
        pass


def test_pipeline_cache_and_sample():
    cs, rs = _runs()
    calls = []

    def counting(s, u):
        calls.append(1)
        return J.mock_backend(s, u)

    path = os.path.join(tempfile.mkdtemp(), "cache.jsonl")
    evidence = {case_id: "[EP_0001_E01] Synthetic evidence." for case_id in cs}
    a = J.judge_runs(rs, evidence, counting, path)
    n1 = len(calls)
    b = J.judge_runs(rs, evidence, counting, path)       # fully served from cache
    assert 0 < n1 <= 2 * len(rs) and len(calls) == n1 and a == b
    assert set(J.mapping_agreement(a)) == set(J.DIMENSIONS)
    assert 0.15 < len(J.stratified_sample(rs, cs)) / len(rs) < 0.35


def test_missing_evidence_rejected():
    _, rs = _runs()
    try:
        J.judge_runs(rs[:1], {}, J.mock_backend)
        assert False, "missing evidence should fail"
    except ValueError:
        pass


def test_spearman():
    assert abs(J.spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1) < 1e-9
    assert abs(J.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1) < 1e-9


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
