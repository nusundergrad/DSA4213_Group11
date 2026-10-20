"""Offline checks for Analyst reuse without changing the demo interface."""
import copy
import json
import subprocess
import sys
from types import SimpleNamespace

from langchain_core.messages import HumanMessage, AIMessage

from src import agent, prompts
from src.benchmark.schemas import Report


def test_supplied_client_does_not_use_demo_model(monkeypatch):
    def unexpected():
        raise AssertionError("demo model")

    monkeypatch.setattr(agent, "get_llm", unexpected)
    messages = [{"role": "user", "content": "Masked evidence"}]
    calls = []
    response = AIMessage(content="HOLD")

    def invoke(sent, **kwargs):
        calls.append((sent, kwargs))
        return response

    assert agent.invoke_analyst(messages, SimpleNamespace(invoke=invoke), temperature=0) is response
    assert calls == [(messages, {"temperature": 0})]


def test_analyst_keeps_state_and_appends_validated_revision(monkeypatch):
    report = {"report_id": "R_test", "recommendation": "HOLD", "rationale": "Limited evidence.",
              "claims": [{"claim_id": f"C{i}", "text": "Demand risk exists.", "evidence_ids": ["E1"], "check_spec": None}
                         for i in (1, 2, 3)]}
    state = {"messages": [HumanMessage(content="Analyze the filing"), AIMessage(content="Previous report")],
             "evidence_packet": {"packet_id": "EP_X"}, "initial_report": report, "final_reports": [report],
             "debate_round": 1, "max_debate_rounds": 3}
    before = copy.deepcopy(state)
    response = AIMessage(content=json.dumps(report))
    calls = []

    def invoke(messages, **kwargs):
        calls.append(messages)
        assert messages[0].content.startswith(prompts.ANALYST_SYSTEM_PROMPT)
        assert json.loads(messages[1].content)["required_report_id"] == "R_test"
        assert messages[2:] == state["messages"]
        return response

    monkeypatch.setattr(agent, "llm", SimpleNamespace(invoke=invoke))
    result = agent.analyst_agent(state)
    assert len(calls) == 1 and state == before
    assert result["messages"] == [response] and response.name == "analyst_agent"
    assert result["final_reports"] == [report, Report.model_validate(report).model_dump(mode="json")]


def test_default_client_is_created_only_once(monkeypatch):
    calls = []
    monkeypatch.setattr(agent, "llm", None)
    monkeypatch.setattr(agent, "load_dotenv", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(agent, "ChatOpenRouter", lambda **kwargs: calls.append(kwargs) or object())
    assert agent.get_llm() is agent.get_llm()
    assert calls == [{"override": True}, {"model": agent.MODEL_NAME, "temperature": 0}]


def test_imports_do_not_load_credentials_clients_or_run_graph():
    for statement in ("import src.agent", "sys.path.insert(0, 'src'); import agent"):
        code = ("import sys, dotenv, langchain_openrouter; "
                "dotenv.load_dotenv = lambda *a, **k: sys.exit(9); "
                "langchain_openrouter.ChatOpenRouter = lambda *a, **k: sys.exit(9); "
                + statement + "; "
                "assert 'src.graph' not in sys.modules and 'graph' not in sys.modules; "
                "assert 'src.tool' not in sys.modules and 'tool' not in sys.modules")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert result.returncode == 0 and not result.stdout, result.stderr


def test_failed_records_keep_the_underlying_error():
    from src.graph import describe_error
    try:
        try:
            raise ValueError("429 rate limited")
        except ValueError as cause:
            raise RuntimeError("risk_manager_agent model failed after 5 attempts") from cause
    except RuntimeError as error:
        text = describe_error(error)
    assert "RuntimeError: risk_manager_agent" in text and "ValueError: 429 rate limited" in text
