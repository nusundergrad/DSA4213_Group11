"""Live Streamlit view for the situation_3 LangGraph execution."""

import sys
import time
from html import escape
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.prepare import load_agent_input
from src.graph import situation_3


st.set_page_config(page_title="Situation 3", layout="wide")
st.title("Situation 3 live execution")

NODE_ORDER = [
    "initial_verifier_node",
    "risk_manager_agent",
    "analyst_agent",
    "verifier_node",
    "trader_agent",
]

DEFAULT_NEXT = {
    "initial_verifier_node": "risk_manager_agent",
    "risk_manager_agent": "analyst_agent",
    "analyst_agent": "verifier_node",
}


def render_graph(statuses, active_from=None, active_node=None, bubble_text=""):
    parts = []
    for index, node in enumerate(NODE_ORDER):
        if active_from is not None or active_node is not None:
            if node == active_from:
                status = "source"
            elif node == active_node:
                status = "target"
            else:
                status = "dull"
        else:
            status = statuses.get(node, "waiting")
        classes = f"node {status}"
        label = node.replace("_", " ").title()
        bubble = ""
        if node == active_from and bubble_text:
            bubble = f'<div class="bubble">{bubble_text}</div>'
        parts.append(
            f'<div class="node-wrap"><div class="{classes}">{label}</div>{bubble}</div>'
        )
        if index < len(NODE_ORDER) - 1:
            next_node = NODE_ORDER[index + 1]
            arrow_class = "arrow visible" if (
                active_from == node and active_node == next_node
            ) else "arrow"
            parts.append(f'<div class="{arrow_class}">➜</div>')

    loop_visible = (
        active_from == "verifier_node"
        and active_node == "risk_manager_agent"
    )
    loop_class = "loop-arrow visible" if loop_visible else "loop-arrow"

    loop_markup = (
        '<div class="loop-connector"><span class="loop-head">◀</span></div>'
        if loop_visible
        else '<div class="loop-connector"></div>'
    )

    st.markdown(
        """
        <style>
        .flow { position:relative; display:flex; align-items:center; gap:12px;
                overflow-x:auto; padding:140px 12px 170px; }
        .node-wrap { position:relative; min-width:145px; text-align:center; }
        .node { width:120px; height:120px; border-radius:50%; margin:auto;
                display:flex; align-items:center; justify-content:center;
                padding:12px; color:white; font-weight:700; font-size:14px;
                background:#64748b; box-shadow:0 3px 10px #0003; }
        .node.source { background:#f59e0b; box-shadow:0 0 0 6px #fde68a, 0 3px 18px #f59e0b88; }
        .node.target { background:#2563eb; box-shadow:0 0 0 6px #93c5fd, 0 3px 18px #2563eb88; }
        .node.dull { opacity:.25; filter:grayscale(1); }
        .node.done { background:#16a34a; }
        .arrow { color:#2563eb; font-size:30px; font-weight:bold; visibility:hidden; }
        .arrow.visible { visibility:visible; animation: pulse .8s ease-in-out; }
        .loop-connector { position:absolute; left:29%; width:38%; top:285px;
                          height:48px; border-bottom:4px solid transparent;
                          border-radius:0 0 50% 50%; visibility:hidden; }
        .loop-connector:after { content:""; position:absolute; left:0; bottom:-12px;
                                border-top:10px solid transparent;
                                border-bottom:10px solid transparent;
                                border-right:16px solid #2563eb; }
        .loop-connector:before { content:""; position:absolute; left:0; right:0;
                                 bottom:-4px; border-bottom:4px solid #2563eb;
                                 border-radius:0 0 50% 50%; }
        .loop-connector.visible { visibility:visible; animation:pulse .8s ease-in-out; }
        .loop-connector:not(:empty) { visibility:visible; }
        @keyframes pulse { 50% { transform:scale(1.25); } }
        .bubble { position:absolute; top:-125px; left:50%; transform:translateX(-50%);
                  background:#fff; border:2px solid #2563eb; border-radius:12px;
                  padding:8px 12px; width:190px; font-size:12px; color:#111827;
                  box-shadow:0 3px 10px #0002; }
        </style>
        """
        + f'<div class="flow">{"".join(parts)}{loop_markup}</div>',
        unsafe_allow_html=True,
    )


def message_snippet(update: dict, limit: int = 150) -> str:
    """Return a compact message/state snippet for the sender's speech bubble."""
    messages = []

    def collect_messages(value):
        if isinstance(value, dict):
            if value.get("messages"):
                messages.extend(value["messages"])
            for child in value.values():
                collect_messages(child)
        elif isinstance(value, list):
            for child in value:
                collect_messages(child)

    collect_messages(update)
    content = None
    for message in reversed(messages):
        message_type = getattr(message, "type", None)
        if isinstance(message, dict):
            message_type = message.get("type") or message.get("role")
        if message_type in ("ai", "assistant"):
            content = getattr(message, "content", None)
            if content is None and isinstance(message, dict):
                content = message.get("content")
            if content:
                break

    if content:
        text = " ".join(str(content).split())
        return escape(text[:limit] + ("..." if len(text) > limit else ""))

    text = " ".join(str(update).split())
    return escape(text[:limit] + ("..." if len(text) > limit else ""))

packet_path = st.text_input(
    "Evidence packet",
    "data/benchmark/public/evidence_packets/EP_0001.json",
)
report_path = st.text_input(
    "Report",
    "data/benchmark/public/reports/EP_0001/clean.json",
)
max_debate_rounds = st.number_input(
    "Maximum debate rounds", min_value=0, value=3, step=1,
)

if st.button("Run graph", type="primary"):
    loaded = load_agent_input(packet_path, report_path, check_clean=False)
    input_content = {
        "content": "Analyze the supplied evidence packet.",
        "evidence_packet": loaded["evidence_packet"],
        "initial_report": loaded["initial_report"],
        "debate_round": 0,
        "max_debate_rounds": max_debate_rounds,
    }

    event_box = st.empty()
    state_box = st.empty()
    statuses = {node: "waiting" for node in NODE_ORDER}
    latest_state = [{}]
    graph_box = st.empty()
    graph_box.empty()

    def display_event(event: dict):
        if event["type"] == "updates":
            node_names = list(event["data"].keys())
            active_node = node_names[0] if node_names else None
            next_node = DEFAULT_NEXT.get(active_node)
            if active_node == "verifier_node":
                debate_round = latest_state[0].get("debate_round", 0)
                max_rounds = latest_state[0].get("max_debate_rounds", max_debate_rounds)
                next_node = (
                    "trader_agent"
                    if debate_round >= max_rounds
                    else "risk_manager_agent"
                )
            for node in node_names:
                if node in statuses:
                    statuses[node] = "done"
            graph_box.empty()
            with graph_box.container():
                render_graph(
                    statuses,
                    active_from=active_node,
                    active_node=next_node,
                    bubble_text=message_snippet(event["data"]),
                )
            event_box.write(f"{active_node} communicating with {next_node}")
            # Keep each communication frame visible before the next node arrives.
            time.sleep(0.75)
        elif event["type"] == "values":
            latest_state[0] = event["data"]
            state_box.write("State updated")

    with st.spinner("Running situation_3..."):
        result = situation_3(input_content, on_event=display_event)

    statuses = {node: "done" for node in NODE_ORDER}
    graph_box.empty()
    with graph_box.container():
        render_graph(statuses)
    st.success("Graph completed")
