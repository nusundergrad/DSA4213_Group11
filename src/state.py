from typing import Any, Annotated, Sequence, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages

class AgentState(TypedDict):
    # Conversation history. Each message should have both ``id`` and ``name``.
    messages: Annotated[Sequence[AnyMessage], add_messages]

    # Frozen benchmark evidence shared by all agents.
    evidence_packet: dict[str, Any]

    # Immutable starting report and latest report after any revisions.
    initial_report: dict[str, Any]
    # Append-only report history. The latest item is the active report.
    final_reports: list[dict[str, Any]]

    # Optional feedback indexed by the message ID being challenged.
    # Example: {"risk_manager:abc123": {"target": "C1", "comment": "..."}}
    risk_feedback: dict[str, Any] | None

    debate_round: int
    max_debate_rounds: int
    # Append-only verifier results; agents can be given only the latest result.
    verifier_reports: list[dict[str, Any]]
    trader_verdict: dict[str, Any] | None
