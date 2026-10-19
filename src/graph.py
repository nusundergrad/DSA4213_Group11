from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from pathlib import Path
import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Literal

try:
    from .agent import analyst_agent, risk_manager_agent, trader_agent
    from .state import AgentState
    from .benchmark.prepare import load_agent_input
    from .benchmark.schemas import Packet, Report
    from .verifier import verifier as run_verifier
except ImportError:
    # Support `python src/graph.py` while preserving src as the package root.
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.agent import analyst_agent, risk_manager_agent, trader_agent
    from src.state import AgentState
    from src.benchmark.prepare import load_agent_input
    from src.benchmark.schemas import Packet, Report
    from src.verifier import verifier as run_verifier

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

    response = graph.invoke({
        "messages": [
            HumanMessage(
                content=input_content["content"],
                id=input_content.get("message_id", "human:initial"),
                name="human",
            )
        ],
        "evidence_packet": input_content["evidence_packet"],
        "initial_report": input_content.get("initial_report", {}),
        "final_reports": [input_content.get("initial_report", {})],
        "risk_feedback": {},
        "debate_round": input_content["debate_round"],
        "max_debate_rounds": input_content["max_debate_rounds"],
        "verifier_reports": [],
        "trader_verdict": None,
    })
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

    response = graph.invoke({
        "messages": [HumanMessage(
            content=input_content["content"],
            id=input_content.get("message_id", "human:initial"),
            name="human",
        )],
        "evidence_packet": input_content["evidence_packet"],
        "initial_report": input_content.get("initial_report", {}),
        "final_reports": [input_content.get("initial_report", {})],
        "risk_feedback": {},
        "debate_round": 0,
        "max_debate_rounds": input_content["max_debate_rounds"],
        "verifier_reports": [],
        "trader_verdict": None,
    })
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

    response = graph.invoke({
        "messages": [HumanMessage(
            content=input_content["content"],
            id=input_content.get("message_id", "human:initial"),
            name="human",
        )],
        "evidence_packet": input_content["evidence_packet"],
        "initial_report": input_content.get("initial_report", {}),
        "final_reports": [input_content.get("initial_report", {})],
        "risk_feedback": {},
        "debate_round": 0,
        "max_debate_rounds": input_content["max_debate_rounds"],
        "verifier_reports": [],
        "trader_verdict": None,
    })
    print("Situation_3 completed", flush=True)
    return response


SITUATIONS = {
    "situation_1": situation_1,
    "situation_2": situation_2,
    "situation_3": situation_3,
}


def _message_record(message):
    return {
        "id": getattr(message, "id", None),
        "name": getattr(message, "name", None),
        "type": getattr(message, "type", None),
        "content": message.content,
    }


def _jsonable_response(response):
    return {
        "messages": [_message_record(message) for message in response.get("messages", [])],
        "initial_report": response.get("initial_report"),
        "final_reports": response.get("final_reports", []),
        "risk_feedback": response.get("risk_feedback"),
        "verifier_reports": response.get("verifier_reports", []),
        "trader_verdict": response.get("trader_verdict"),
        "debate_round": response.get("debate_round"),
    }


def run_from_files(
    packet_path: str | Path,
    report_path: str | Path,
    *,
    situation: str = "situation_1",
    max_debate_rounds=3,
):
    if not situation.startswith("situation_"):
        situation = f"situation_{situation}"
    if situation not in SITUATIONS:
        available = ", ".join(sorted(SITUATIONS))
        raise ValueError(f"Unknown situation '{situation}'. Available: {available}")

    loaded = load_agent_input(packet_path, report_path, check_clean=False)
    return SITUATIONS[situation]({
        "content": "Analyze the supplied evidence packet.",
        "evidence_packet": loaded["evidence_packet"],
        "initial_report": loaded["initial_report"],
        "debate_round": 0,
        "max_debate_rounds": max_debate_rounds,
    })


def run_batch(
    cases_path: str | Path = "output/cases.json",
    *,
    dataset_root: str | Path = "data/benchmark/public",
    output_root: str | Path = "output",
    max_debate_rounds: int = 3,
):
    """Run every case in a JSON list and save one evaluation record per case.

    Each case contains evidence_packet, report, and situation. Names are
    resolved under dataset_root/evidence_packets and dataset_root/reports.
    """
    cases_path = Path(cases_path)
    dataset_root = Path(dataset_root)
    output_root = Path(output_root)
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("The cases JSON must contain a list of dictionaries")

    results = []
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
        case_output = output_root / packet_id / situation / report_name
        case_output.mkdir(parents=True, exist_ok=True)

        try:
            response = run_from_files(
                packet_path,
                report_path,
                situation=situation,
                max_debate_rounds=max_debate_rounds,
            )
            record = {
                "status": "completed",
                "evidence_packet": packet_id,
                "report": report_name,
                "situation": situation,
                "packet_path": str(packet_path),
                "report_path": str(report_path),
                **_jsonable_response(response),
            }
        except Exception as error:
            print(
                f"Case failed: {packet_id}/{situation}/{report_name}",
                flush=True,
            )
            traceback.print_exc()
            record = {
                "status": "failed",
                "evidence_packet": packet_id,
                "report": report_name,
                "situation": situation,
                "packet_path": str(packet_path),
                "report_path": str(report_path),
                "error": str(error),
            }

        run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        record["run_timestamp"] = run_timestamp
        (case_output / f"{run_timestamp}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        results.append(record)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet")
    parser.add_argument("--report")
    parser.add_argument("--situation", default="situation_1")
    args = parser.parse_args()
    if args.packet and args.report:
        run_from_files(args.packet, args.report, situation=args.situation)
    else:
        run_batch()
