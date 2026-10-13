"""Offline checks for Analyst reuse without changing the demo interface."""
import copy
import json
import subprocess
import sys
from types import SimpleNamespace

from langchain_core.messages import HumanMessage, AIMessage

from src import agent, prompts


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


def test_legacy_analyst_keeps_messages_and_state(monkeypatch):
    state = {"ticker": "AAA", "date": "2023", "messages": [
        HumanMessage(content="Analyze the filing"), AIMessage(content="Previous report")],
        "debate_round": 1, "max_debate_rounds": 3}
    before = copy.deepcopy(state)
    filing = {"content": "Synthetic filing excerpt"}

    def retrieve(query):
        assert query == {"ticker": "AAA", "date": "2023"}
        return filing

    monkeypatch.setitem(sys.modules, "src.tool", SimpleNamespace(
        mock_retrieve_10k_filing=SimpleNamespace(invoke=retrieve)))
    response = AIMessage(content="HOLD; synthetic analysis.")
    calls = []

    def invoke(messages):
        calls.append(messages)
        assert messages[0].content == prompts.ANALYST_SYSTEM_PROMPT
        assert "AAA" in messages[1].content
        assert json.loads(messages[2].content) == filing
        assert messages[3:] == state["messages"]
        return response

    monkeypatch.setattr(agent, "llm", SimpleNamespace(invoke=invoke))
    result = agent.analyst_agent(state)
    assert len(calls) == 1 and state == before
    assert result == {"messages": [response]}
    assert response.name == "analyst_agent_response"


def test_default_client_is_created_only_once(monkeypatch):
    calls = []
    monkeypatch.setattr(agent, "llm", None)
    monkeypatch.setattr(agent, "load_dotenv", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(agent, "ChatOpenRouter", lambda **kwargs: calls.append(kwargs) or object())
    assert agent.get_llm() is agent.get_llm()
    assert calls == [{"override": True}, {"model": "openrouter/free", "temperature": 0}]


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
