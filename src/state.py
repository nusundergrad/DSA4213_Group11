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

    # Structured Risk Manager turns: {round, challenges, calibration_concern, overall_assessment, text}.
    risk_manager_turns: list[dict[str, Any]]
    # What each Analyst revision actually changed: {round, edited/reverted/retracted claim ids}.
    analyst_revision_turns: list[dict[str, Any]]
    # One entry per accepted model response: agent, input/output tokens, latency.
    usage_log: list[dict[str, Any]]
    # Fixed sentence shown with the Analyst's report (tone variants); never part of the report itself.
    confidence_framing: str | None
