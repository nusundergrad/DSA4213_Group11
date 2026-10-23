"""All four situations end to end with a scripted fake model (no network, no API key)."""
import json
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from src import agent, graph, prompts
from src.benchmark.prepare import ROOT

PACKET = ROOT / "public/evidence_packets/EP_0001.json"
REPORT = ROOT / "public/reports/EP_0001/error_03_arithmetic.json"


class FakeLLM:
    """Plays all three roles; remembers what each role was shown."""

    def __init__(self):
        self.seen = {"risk": [], "analyst": [], "trader": []}

    def invoke(self, messages, **kwargs):
        system = messages[0].content
        if "Head of Risk Management" in system:
            assert prompts.NUMERICAL_PRECISION_INSTRUCTIONS in system
            context = json.loads(messages[1].content)
            self.seen["risk"].append(context)
            body = {"challenges": [{"target_claim_id": "C1", "defect_type": "arithmetic", "evidence_ids": [],
                                    "explanation": "Growth is 6.43%, not 16.43%.", "requested_change": "Fix C1."}],
                    "calibration_concern": None, "overall_assessment": "Not proportionate."}
        elif "Senior Financial Analyst" in system:
            assert prompts.NUMERICAL_PRECISION_INSTRUCTIONS in system
            report = json.loads(messages[1].content)["current_report"]
            self.seen["analyst"].append(report)
            report["claims"][0]["text"] = "Revised C1."
            report["claims"][1]["text"] = "Unrequested change to C2."     # must be reverted
            body = report
        else:
            context = json.loads(messages[1].content.split("decision:\n", 1)[1].rsplit("\nReturn", 1)[0])
            self.seen["trader"].append(context)
            body = {"assessment": "ACCEPT", "support_score": 70, "investment_action": "HOLD",
                    "relied_on_claim_ids": ["C1"], "rationale": "Supported."}
        return AIMessage(content=json.dumps(body), usage_metadata={"input_tokens": 10, "output_tokens": 5,
                                                                   "total_tokens": 15})


@pytest.fixture
def fake(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(agent, "llm", llm)
    return llm


def run(situation, **kw):
    return graph.run_from_files(PACKET, REPORT, situation=situation, max_debate_rounds=2, **kw)


def test_baseline_trader_decides_alone_and_sees_the_packet(fake):
    out = run("situation_0")
    assert not out["risk_manager_turns"] and not out["verifier_reports"]
    verdict = out["trader_verdict"]
    assert verdict["support_score"] == 70 and verdict["relied_on_claim_ids"] == ["C1"]
    assert 'evidence_packet' not in fake.seen['trader'][0]              # main's information boundary
    assert len(out["usage_log"]) == 1


def test_debate_has_structured_challenges_without_giving_trader_full_discussion(fake):
    out = run("situation_1")
    turns = out["risk_manager_turns"]
    assert [t["round"] for t in turns] == [1, 2]
    assert turns[0]["challenges"][0]["challenge_id"] == "RM_R1_01" and turns[1]["challenges"][0]["challenge_id"] == "RM_R2_01"
    assert turns[0]["structured"] is True
    assert 'discussion' not in fake.seen['trader'][0]
    assert len(out["usage_log"]) == 5 and all(u["input_tokens"] == 10 for u in out["usage_log"])


def test_actual_revisions_are_preserved_so_new_errors_remain_observable(fake):
    out = run("situation_1")
    initial, final = out["initial_report"], out["final_reports"][-1]
    assert final["claims"][0]["text"] == "Revised C1."                    # challenged: may change
    assert final['claims'][1]['text'] == 'Unrequested change to C2.'
    assert set(out['analyst_revision_turns'][0]['edited_claim_ids']) == {'C1', 'C2'}


def test_hybrid_verifies_initial_report_and_every_revision(fake):
    out = run("situation_3")
    assert len(out["verifier_reports"]) == 3                             # initial + after each of 2 revisions
    assert out["verifier_reports"][0]["claim_results"]["C1"] is False    # the planted arithmetic defect
    assert fake.seen["risk"][0]["latest_verifier_report"]["claim_results"]["C1"] is False


def test_verification_only_makes_one_model_call(fake):
    out = run("situation_2")
    assert len(out["usage_log"]) == 1 and out["verifier_reports"]


def test_tone_adds_a_fixed_sentence_beside_the_report_not_in_it(fake):
    out = run("situation_1", tone="overconfident")
    assert fake.seen["risk"][0]["analyst_note"] == "I have high confidence in this assessment."
    assert fake.seen["trader"][0]["analyst_note"] == "I have high confidence in this assessment."
    assert "high confidence in this assessment" not in json.dumps(out["initial_report"])
    with pytest.raises(ValueError, match="Unknown tone"):
        run("situation_1", tone="shouting")


def test_challenge_against_an_unknown_claim_is_rejected_and_retried(monkeypatch, fake):
    monkeypatch.setattr(agent, 'MAX_MODEL_RETRIES', 2)
    monkeypatch.setattr(agent, "RETRY_BASE_DELAY_SECONDS", 0)
    calls = []
    real = fake.invoke

    def flaky(messages, **kw):
        if "Head of Risk Management" in messages[0].content and not calls:
            calls.append(1)
            return AIMessage(content=json.dumps({"challenges": [{"target_claim_id": "C9", "defect_type": "arithmetic",
                             "explanation": "x", "requested_change": "y"}], "overall_assessment": "z"}))
        return real(messages, **kw)

    monkeypatch.setattr(fake, "invoke", flaky)
    assert run("situation_1")["risk_manager_turns"][0]["challenges"][0]["target_claim_id"] == "C1"
    assert calls


def test_rationale_challenge_is_preserved_without_inventing_a_claim_id(monkeypatch, fake):
    original = fake.invoke

    def review(messages, **kwargs):
        response = original(messages, **kwargs)
        if 'Head of Risk Management' in messages[0].content:
            body = json.loads(response.content)
            body['challenges'][0].update(target_claim_id=None, defect_type='unsupported_inference',
                                         explanation='The rationale guarantees returns without supporting evidence.')
            response.content = json.dumps(body)
        return response

    monkeypatch.setattr(fake, 'invoke', review)
    out = run('situation_1')
    assert out['risk_manager_turns'][0]['challenges'][0]['target_claim_id'] is None


def test_batch_records_are_complete_resumable_and_adaptable(fake, tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "evaluation"))
    from benchmark_cases import build_cases, load_clean_report
    from graph_adapter import adapt_all, load_records
    from auto_scoring import auto_score_run
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(json.dumps([
        {"evidence_packet": "EP_0001", "report": "error_03_arithmetic", "situation": s, "tone": t}
        for s, t in ((0, "neutral"), (1, "neutral"), (3, "neutral"), (1, "underconfident"))]))
    kw = dict(dataset_root=ROOT / "public", output_root=tmp_path / "out", max_debate_rounds=2)
    assert len(graph.run_batch(cases_file, **kw)) == 4
    assert graph.run_batch(cases_file, **kw) == []                       # all completed: nothing re-run
    records = load_records(tmp_path / "out")
    assert {r["status"] for r in records} == {"completed"}
    cases, manifest = build_cases()
    runs = adapt_all(records, cases)
    assert {(r.architecture, r.tone) for r in runs} == {
        ("baseline", "neutral"), ("debate", "neutral"), ("hybrid", "neutral"), ("debate", "underconfident")}
    debate = next(r for r in runs if (r.architecture, r.tone) == ("debate", "neutral"))
    assert debate.risk_manager_turns[0]["challenges"][0]["defect_type"] == "arithmetic"
    assert debate.trader["support_score"] == 70 and debate.trader["relied_on_claim_ids"] == ["C1"]
    assert debate.usage["input_tokens"] == 50 and debate.config["model"]
    assert all(r['input_sha256'] and r['config_sha256'] for r in records)
    assert all(len(r['model_calls']) == r['usage']['calls'] for r in records)
    with pytest.raises(ValueError, match='Run plan differs'):
        graph.run_batch(cases_file, **{**kw, 'max_debate_rounds': 3})
    score = auto_score_run(debate, cases[debate.case_id], load_clean_report(manifest[debate.case_id]))
    assert score.risk_manager_detected is None                           # matching type+value is only a suggestion
    assert score.scoring_provenance["rm_suggestion"] is True
