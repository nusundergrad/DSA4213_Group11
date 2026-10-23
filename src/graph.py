from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from pathlib import Path
import argparse
import json
import hashlib
import time
import sys
import traceback
from datetime import datetime, timezone
from typing import Literal

try:
    from . import agent as agent_module
    from .agent import analyst_agent, risk_manager_agent, trader_agent, MODEL_NAME as _MODEL
    from .state import AgentState
    from .benchmark.prepare import load_agent_input
    from .benchmark.schemas import Packet, Report
    from .verifier import verifier as run_verifier
except ImportError:
    # Support `python src/graph.py` while preserving src as the package root.
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.agent import analyst_agent, risk_manager_agent, trader_agent, MODEL_NAME as _MODEL
    from src import agent as agent_module
    from src.state import AgentState
    from src.benchmark.prepare import load_agent_input
    from src.benchmark.schemas import Packet, Report
    from src.verifier import verifier as run_verifier

def get_model_name() -> str:
    return agent_module.MODEL_NAME


def next_after_analyst(state: AgentState) -> Literal["risk_manager_agent", "trader_agent"]:
    print(
        "Routing after Analyst:",
        f"debate_round={state['debate_round']}",
        f"max_debate_rounds={state['max_debate_rounds']}",
        flush=True,
    )
    if state["debate_round"] >= state["max_debate_rounds"]:
        print("Conditional edge selected: trader_agent", flush=True)
        return "trader_agent"
    print("Conditional edge selected: risk_manager_agent", flush=True)
    return "risk_manager_agent"


def verifier_node(state: AgentState):
    print("Verifier node invoked.")
    packet = Packet.model_validate(state["evidence_packet"])
    report_history = state.get("final_reports") or []
    report = Report.model_validate(report_history[-1])
    result = run_verifier(report, packet)
    verifier_record = {
        "report_id": report.report_id,
        "report_sha256": content_hash(report.model_dump(mode='json')),
        "scope": "Structured numerical assertions only. null means NOT_CHECKABLE; PASS does not certify prose or reasoning.",
        "claim_results": result,
    }
    return {
        "verifier_reports": [
            *state.get("verifier_reports", []),
            verifier_record,
        ]
    }


def initial_verifier_node(state: AgentState):
    """Verify the frozen initial report before the debate starts."""
    return verifier_node(state)



CONFIDENCE_FRAMING = {
    "underconfident": "I have low confidence in this assessment.",
    "neutral": "I have moderate confidence in this assessment.",
    "overconfident": "I have high confidence in this assessment.",
}


def _initial_state(input_content: dict, debate_round: int) -> dict:
    """Starting graph state, identical for every situation so conditions differ only in the graph."""
    initial_report = input_content.get("initial_report", {})
    return {
        "messages": [HumanMessage(
            content=input_content["content"],
            id=input_content.get("message_id", "human:initial"),
            name="human",
        )],
        "evidence_packet": input_content["evidence_packet"],
        "initial_report": initial_report,
        "final_reports": [initial_report],
        "risk_feedback": {},
        "debate_round": debate_round,
        "max_debate_rounds": input_content["max_debate_rounds"],
        "verifier_reports": [],
        "trader_verdict": None,
        "risk_manager_turns": [],
        "analyst_revision_turns": [],
        "usage_log": [],
        "confidence_framing": input_content.get("confidence_framing"),
    }


def situation_0(input_content: dict):
    """Baseline: the Trader judges the initial report with no debate and no verifier."""
    print("Starting situation_0", flush=True)
    graph = StateGraph(AgentState)
    graph.add_node(trader_agent)
    graph.add_edge(START, "trader_agent")
    graph.add_edge("trader_agent", END)
    response = graph.compile().invoke(_initial_state(input_content, 0))
    print("Situation_0 completed", flush=True)
    return response


def situation_1(input_content: dict):
    print("Starting situation_1", flush=True)
    graph = StateGraph(AgentState)
    graph.add_node(analyst_agent)
    graph.add_node(risk_manager_agent)
    graph.add_node(trader_agent)
    # The initial report is already loaded in state, so begin with Risk Manager.
    graph.add_edge(START, "risk_manager_agent")
    graph.add_edge("risk_manager_agent", "analyst_agent")
    #
    graph.add_conditional_edges(
        "analyst_agent",
        next_after_analyst,
        {
            "risk_manager_agent": "risk_manager_agent",
            "trader_agent": "trader_agent",
        },
    )
    graph.add_edge("trader_agent", END)
    graph = graph.compile()

    response = graph.invoke(_initial_state(input_content, input_content["debate_round"]))
    print("Situation_1 completed", flush=True)
    return response

def situation_2(input_content: dict):
    print("Starting situation_2", flush=True)
    graph = StateGraph(AgentState)
    graph.add_node(verifier_node)
    graph.add_node(trader_agent)
    graph.add_edge(START, "verifier_node")
    graph.add_edge("verifier_node", "trader_agent")
    graph.add_edge("trader_agent", END)
    graph = graph.compile()

    response = graph.invoke(_initial_state(input_content, 0))
    print("Situation_2 completed", flush=True)
    return response


def situation_3(input_content: dict):
    print("Starting situation_3", flush=True)
    graph = StateGraph(AgentState)
    graph.add_node(analyst_agent)
    graph.add_node(verifier_node)
    graph.add_node(initial_verifier_node)
    graph.add_node(risk_manager_agent)
    graph.add_node(trader_agent)
    # The initial verifier has one fixed destination.
    graph.add_edge(START, "initial_verifier_node")
    graph.add_edge("initial_verifier_node", "risk_manager_agent")
    graph.add_edge("risk_manager_agent", "analyst_agent")
    graph.add_edge("analyst_agent", "verifier_node")
    graph.add_conditional_edges(
        "verifier_node",
        next_after_analyst,
        {
            "risk_manager_agent": "risk_manager_agent",
            "trader_agent": "trader_agent",
        },
    )
    graph.add_edge("trader_agent", END)
    graph = graph.compile()

    response = graph.invoke(_initial_state(input_content, 0))
    print("Situation_3 completed", flush=True)
    return response

def test_verifier(input_content: dict):
    print("Starting test_verifier", flush=True)
    graph = StateGraph(AgentState)
    graph.add_node(verifier_node)
    graph.add_edge(START, "verifier_node")
    graph.add_edge("verifier_node", END)
    graph = graph.compile()

    response = graph.invoke(_initial_state(input_content, 0))
    print("test_verifier completed", flush=True)
    return response

SITUATIONS = {
    "situation_0": situation_0,
    "situation_1": situation_1,
    "situation_2": situation_2,
    "situation_3": situation_3,
}


def describe_error(error: BaseException) -> str:
    """The error plus its causes, so a record shows the real failure (e.g. the API's 429), not just
    'model failed after N attempts'."""
    parts, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        parts.append(f"{type(error).__name__}: {error}")
        error = error.__cause__ or error.__context__
    return " <- ".join(parts)


def _message_record(message):
    return {
        "id": getattr(message, "id", None),
        "name": getattr(message, "name", None),
        "type": getattr(message, "type", None),
        "content": message.content,
    }


def summarize_usage(usage_log: list) -> dict:
    """Totals over accepted responses. A total is None when no response reported that figure."""
    def total(key):
        values = [u[key] for u in usage_log if u.get(key) is not None]
        return sum(values) if values else None
    return {"input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
            "latency_ms": total("latency_ms"), "estimated_cost_usd": total("estimated_cost_usd"),
            "calls": len(usage_log), "per_call": usage_log}


def _jsonable_response(response):
    return {
        "messages": [_message_record(message) for message in response.get("messages", [])],
        "initial_report": response.get("initial_report"),
        "final_reports": response.get("final_reports", []),
        "risk_feedback": response.get("risk_feedback"),
        "verifier_reports": response.get("verifier_reports", []),
        "trader_verdict": response.get("trader_verdict"),
        "debate_round": response.get("debate_round"),
        "risk_manager_turns": response.get("risk_manager_turns", []),
        "analyst_revision_turns": response.get("analyst_revision_turns", []),
        "usage": summarize_usage(response.get("usage_log", [])),
    }


def run_from_files(
    packet_path: str | Path,
    report_path: str | Path,
    *,
    situation: str = "situation_1",
    max_debate_rounds=3,
    tone: str = "neutral",
):
    situation = str(situation)
    if tone not in CONFIDENCE_FRAMING:
        raise ValueError(f"Unknown tone {tone!r}. Available: {', '.join(CONFIDENCE_FRAMING)}")
    if not situation.startswith("situation_"):
        situation = f"situation_{situation}"
    if situation not in SITUATIONS:
        available = ", ".join(sorted(SITUATIONS))
        raise ValueError(f"Unknown situation '{situation}'. Available: {available}")
    if situation in ('situation_1', 'situation_3') and max_debate_rounds < 1:
        raise ValueError('Debate and hybrid require at least one round')

    loaded = load_agent_input(packet_path, report_path, check_clean=False)
    return SITUATIONS[situation]({
        "content": "Analyze the supplied evidence packet.",
        "evidence_packet": loaded["evidence_packet"],
        "initial_report": loaded["initial_report"],
        "debate_round": 0,
        "max_debate_rounds": max_debate_rounds,
        "confidence_framing": CONFIDENCE_FRAMING[tone],
    })


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def completed_record_exists(case_output: Path, input_sha256=None, config_sha256=None) -> bool:
    for path in sorted(case_output.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if record.get('status') == 'completed':
            if input_sha256 and (record.get('input_sha256') != input_sha256 or record.get('config_sha256') != config_sha256):
                raise ValueError('Existing run has different inputs/configuration; choose a new output folder')
            return True
    return False


def run_batch(
    cases_path: str | Path = "output/cases.json",
    *,
    dataset_root: str | Path = "data/benchmark/public",
    output_root: str | Path = "output",
    max_debate_rounds: int = 3,
    skip_completed: bool = True,
):
    """Run every case in a JSON list and save one evaluation record per case.

    Each case contains evidence_packet, report, and situation (0 baseline, 1 debate, 2 verification,
    3 hybrid), and optionally tone (underconfident, neutral, overconfident; default neutral). Names are
    resolved under dataset_root/evidence_packets and dataset_root/reports. With skip_completed (the
    default) a condition that already has a completed record is not run again, so an interrupted or
    rate-limited batch can simply be started again.
    """
    cases_path = Path(cases_path)
    dataset_root = Path(dataset_root)
    output_root = Path(output_root)


    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("The cases JSON must contain a list of dictionaries")

    results = []
    config = {'model': get_model_name(), 'temperature': 0, 'max_debate_rounds': max_debate_rounds,
              'max_tokens': agent_module.MAX_TOKENS, 'max_model_attempts': agent_module.MAX_MODEL_RETRIES,
              'reasoning_effort': agent_module.REASONING_EFFORT,
              'trader_evidence_access': False,
              'code_sha256': {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                             for name in ('agent.py', 'graph.py', 'prompts.py', 'verifier.py')}}
    output_root.mkdir(parents=True, exist_ok=True)
    plan = {'cases': cases, 'config': config}
    plan_path = output_root / 'run_plan.json'
    if plan_path.exists() and json.loads(plan_path.read_text(encoding='utf-8')) != plan:
        raise ValueError('Run plan differs; choose a new output folder')
    plan_path.write_text(json.dumps(plan, indent=2), encoding='utf-8')
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"Case {index} must be a dictionary")
        for key in ("evidence_packet", "report", "situation"):
            if key not in case:
                raise ValueError(f"Case {index} is missing '{key}'")

        packet_id = str(case["evidence_packet"])
        report_name = str(case["report"])
        situation = str(case["situation"])
        if not situation.startswith("situation_"):
            situation = f"situation_{situation}"

        packet_path = dataset_root / "evidence_packets" / f"{packet_id}.json"
        report_path = dataset_root / "reports" / packet_id / f"{report_name}.json"
        tone = str(case.get("tone", "neutral"))
        loaded = load_agent_input(packet_path, report_path, check_clean=False)
        input_hash = content_hash(loaded)
        config_hash = content_hash({**config, 'situation': situation, 'tone': tone})
        case_output = output_root / packet_id / situation / report_name
        if tone != "neutral":
            case_output = case_output / tone
        if skip_completed and completed_record_exists(case_output, input_hash, config_hash):
            print(f"Skipping completed: {packet_id}/{situation}/{report_name}/{tone}", flush=True)
            continue
        case_output.mkdir(parents=True, exist_ok=True)
        identity = {
            "evidence_packet": packet_id,
            "report": report_name,
            "situation": situation,
            "tone": tone,
            "confidence_framing": CONFIDENCE_FRAMING.get(tone),
            "packet_path": str(packet_path),
            "report_path": str(report_path),
            'input_sha256': input_hash, 'config_sha256': config_hash,
            'initial_report': loaded['initial_report'], 'evidence_packet_snapshot': loaded['evidence_packet'],
            'config': config,
            'started_at': datetime.now(timezone.utc).isoformat(),
        }

        calls = []
        token = agent_module.MODEL_CALLS.set(calls)
        started = time.perf_counter()
        try:
            response = run_from_files(
                packet_path,
                report_path,
                situation=situation,
                max_debate_rounds=max_debate_rounds,
                tone=tone,
            )
            record = {"status": "completed", **identity, **_jsonable_response(response)}
        except Exception as error:
            print(
                f"Case failed: {packet_id}/{situation}/{report_name}",
                flush=True,
            )
            traceback.print_exc()
            record = {"status": "failed", **identity, "error": describe_error(error)}
        finally:
            agent_module.MODEL_CALLS.reset(token)

        record['model_calls'] = calls
        record['usage'] = summarize_usage([c.get('usage', {'latency_ms': c['latency_ms']}) for c in calls])
        record['usage']['wall_latency_ms'] = round((time.perf_counter() - started) * 1000)
        record['finished_at'] = datetime.now(timezone.utc).isoformat()

        run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        record["run_timestamp"] = run_timestamp
        (case_output / f"{run_timestamp}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        results.append(record)
        if record['status'] == 'failed' and any(code in record.get('error', '') for code in ('401', '402', '403', '429')):
            print('Authentication/quota error: saved the failed attempt; stopping this batch.', flush=True)
            break

    return results

def situation_verifier():
    dataset_root = Path("data/benchmark/public")
    packet_id = "EP_0001"
    report_name = "clean"
    packet_path = dataset_root / "evidence_packets" / f"{packet_id}.json"
    report_path = dataset_root / "reports" / packet_id / f"{report_name}.json"
   
    loaded = load_agent_input(packet_path, report_path, check_clean=False)
    return test_verifier({
        "content": "Analyze the supplied evidence packet.",
        "evidence_packet": loaded["evidence_packet"],
        "initial_report": loaded["initial_report"],
        "max_debate_rounds": 0,
    })



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet")
    parser.add_argument("--report")
    parser.add_argument("--situation", default="situation_1")
    parser.add_argument("--verifier")
    parser.add_argument('--cases', default='output/cases.json')
    parser.add_argument('--dataset-root', default='data/benchmark/public')
    parser.add_argument('--output-root', default='output')
    parser.add_argument('--model', default=get_model_name())
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--tone', choices=list(CONFIDENCE_FRAMING), default='neutral')
    parser.add_argument('--max-attempts', type=int, default=1)
    parser.add_argument('--max-tokens', type=int, default=6000)
    parser.add_argument('--reasoning-effort', choices=['none', 'low', 'medium', 'high'])
    args = parser.parse_args()
    if args.model in ('openrouter/free', 'openrouter/auto') or args.max_attempts < 1:
        parser.error('Use an explicit model ID and a positive attempt count')
    agent_module.MODEL_NAME = args.model
    agent_module.MAX_MODEL_RETRIES = args.max_attempts
    agent_module.MAX_TOKENS = args.max_tokens
    agent_module.REASONING_EFFORT = args.reasoning_effort
    if args.packet and args.report:
        run_from_files(args.packet, args.report, situation=args.situation, max_debate_rounds=args.rounds, tone=args.tone)
    elif args.verifier:
        print(situation_verifier())
    else:
        run_batch(args.cases, dataset_root=args.dataset_root, output_root=args.output_root, max_debate_rounds=args.rounds)
