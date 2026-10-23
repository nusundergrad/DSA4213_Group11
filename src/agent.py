from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from dotenv import load_dotenv
if __package__:
    from .state import AgentState
    from .prompts import ANALYST_SYSTEM_PROMPT, RISK_MANAGER_SYSTEM_PROMPT, TRADER_SYSTEM_PROMPT
    from .prompts import NUMERICAL_PRECISION_INSTRUCTIONS
    from .benchmark.schemas import Report
else:
    from state import AgentState
    from prompts import ANALYST_SYSTEM_PROMPT, RISK_MANAGER_SYSTEM_PROMPT, TRADER_SYSTEM_PROMPT
    from prompts import NUMERICAL_PRECISION_INSTRUCTIONS
    from benchmark.schemas import Report
import json
import os
import re
import time
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

llm = None
# MODEL_NAME = "openrouter/free"
MODEL_NAME = "nvidia/nemotron-3.5-lightning:free"
MAX_MODEL_RETRIES = 1
RETRY_BASE_DELAY_SECONDS = 5.0   # waits 5, 10, 20, 40 s: short waits do not outlast a free-tier rate limit
MAX_TOKENS = 6000
REASONING_EFFORT = None
MODEL_CALLS = ContextVar('model_calls', default=None)
CURRENT_CALL = ContextVar('current_call', default=None)


CHALLENGE_TYPES = ("wrong_number", "arithmetic", "reporting_period", "citation_misattribution",
                   "direct_factual_contradiction", "material_omission", "unsupported_inference")


class Challenge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: str | None = None          # assigned by the runner (RM_R1_01, ...), not by the model
    target_claim_id: str | None             # null for rationale errors or an omitted claim
    defect_type: Literal["wrong_number", "arithmetic", "reporting_period", "citation_misattribution",
                         "direct_factual_contradiction", "material_omission", "unsupported_inference"]
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str
    requested_change: str


class RiskManagerTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenges: list[Challenge]
    calibration_concern: str | None = None
    overall_assessment: str


class TraderDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment: Literal["ACCEPT", "REJECT"]
    support_score: float = Field(ge=0, le=100)
    investment_action: Literal["BUY", "HOLD", "SELL"]
    relied_on_claim_ids: list[str]
    rationale: str


def make_message_id(agent_name: str) -> str:
    """Create a globally unique, human-readable message ID for this run."""
    return f"{agent_name}:{uuid4().hex}"


def label_message(message, agent_name: str):
    """Attach the agent label and a unique ID to a LangChain message."""
    message.name = agent_name
    if not getattr(message, "id", None):
        message.id = make_message_id(agent_name)
    return message


def latest_report(state: AgentState) -> dict:
    """Return only the current report for use in an agent prompt."""
    reports = state.get("final_reports") or []
    return reports[-1] if reports else state.get("initial_report", {})


def append_report(state: AgentState, report: dict) -> dict:
    """Return a new report history with the revised report appended."""
    return [*(state.get("final_reports") or []), report]


def parse_report_response(content: str) -> Report:
    """Parse strict JSON, with a fallback for a single fenced JSON object."""
    try:
        return Report.model_validate_json(content)
    except Exception as direct_error:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if not match:
            raise direct_error
        return Report.model_validate_json(match.group(1))


def _parse_json_model(model, content: str):
    try:
        return model.model_validate_json(content)
    except Exception as direct_error:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if not match:
            raise direct_error
        return model.model_validate_json(match.group(1))


def parse_trader_response(content: str) -> TraderDecision:
    return _parse_json_model(TraderDecision, content)


def parse_risk_manager_response(content: str) -> RiskManagerTurn:
    return _parse_json_model(RiskManagerTurn, content)


def claim_ids(state: AgentState) -> set:
    return {claim["claim_id"] for claim in latest_report(state)["claims"]}


def check_risk_manager_turn(turn: RiskManagerTurn, state: AgentState) -> None:
    """Challenges must point at claims and evidence that exist; an invented target cannot be scored."""
    known_claims = claim_ids(state)
    known_evidence = {e["evidence_id"] for e in state["evidence_packet"].get("evidence", [])}
    for challenge in turn.challenges:
        if challenge.target_claim_id is not None and challenge.target_claim_id not in known_claims:
            raise ValueError(f"challenge targets unknown claim {challenge.target_claim_id!r}; known: {sorted(known_claims)}")
        if not set(challenge.evidence_ids) <= known_evidence:
            raise ValueError("challenge cites evidence IDs that are not in the packet")


def number_challenges(turn: RiskManagerTurn, round_no: int) -> dict:
    """Unique, deterministic challenge IDs (RM_R1_01); the model does not invent them."""
    data = turn.model_dump(mode="json")
    for i, challenge in enumerate(data["challenges"], start=1):
        challenge["challenge_id"] = f"RM_R{round_no}_{i:02d}"
    return data


def check_trader_decision(decision: TraderDecision, state: AgentState) -> None:
    unknown = set(decision.relied_on_claim_ids) - claim_ids(state)
    if unknown:
        raise ValueError(f"relied_on_claim_ids names unknown claims {sorted(unknown)}")






def usage_entry(agent_name: str, response) -> dict:
    """Tokens and latency of one accepted response. Unavailable values stay None, never 0."""
    metadata = getattr(response, "response_metadata", {}) or {}
    tokens = getattr(response, "usage_metadata", None) or {}
    return {"agent": agent_name,
            "input_tokens": tokens.get("input_tokens"), "output_tokens": tokens.get("output_tokens"),
            "latency_ms": metadata.get("latency_ms"),
            "estimated_cost_usd": (metadata.get("token_usage") or {}).get("cost")}


def with_usage(state: AgentState, agent_name: str, response) -> list:
    return [*(state.get("usage_log") or []), usage_entry(agent_name, response)]


def analyst_note(state: AgentState):
    """The fixed confidence sentence shown beside the report (tone variants), or None."""
    return state.get("confidence_framing")


def latest_verifier_report(state: AgentState) -> dict | None:
    """Return verification only when it belongs to the latest report."""
    report = latest_report(state)
    report_id = report.get("report_id") if report else None
    for verifier_report in reversed(state.get("verifier_reports") or []):
        if verifier_report.get("report_id") == report_id:
            if verifier_report.get('report_sha256'):
                import hashlib
                digest = hashlib.sha256(json.dumps(report, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
                if digest != verifier_report['report_sha256']:
                    continue
            return verifier_report
    return None


def get_llm():
    global llm
    if llm is None:
        from httpx import Client
        from openrouter import OpenRouter
        load_dotenv(Path(__file__).parent / '.env', override=True)
        load_dotenv(Path(__file__).parents[1] / '.env', override=True)

        def save_request(request):
            if CURRENT_CALL.get() is not None:
                CURRENT_CALL.get()['request'] = json.loads(request.content)

        def save_response(response):
            response.read()
            if CURRENT_CALL.get() is not None:
                CURRENT_CALL.get()['raw_response'] = response.text

        http = Client(event_hooks={'request': [save_request], 'response': [save_response]})
        sdk = OpenRouter(api_key=os.environ['OPENROUTER_API_KEY'], client=http,
                         retry_config=None, timeout_ms=180000)
        llm = ChatOpenRouter(model=MODEL_NAME, temperature=0, client=sdk,
                             max_tokens=MAX_TOKENS, max_retries=0)
    return llm


def log_model_call(agent_name: str, messages, model_client=None):
    client = model_client or get_llm()
    configured_model = getattr(client, "model", None) or getattr(client, "model_name", None)
    print(
        f"[{agent_name}] calling model={configured_model or MODEL_NAME} "
        f"messages={len(messages)}",
        flush=True,
    )


def log_model_response(agent_name: str, response):
    metadata = getattr(response, "response_metadata", {}) or {}
    returned_model = metadata.get("model_name") or metadata.get("model")
    print(
        f"[{agent_name}] returned model={returned_model or 'unknown'} "
        f"response_type={type(response.content).__name__}",
        flush=True,
    )


def invoke_with_retry(agent_name: str, messages, validator=None, **kwargs):
    last_error = None
    for attempt in range(1, MAX_MODEL_RETRIES + 1):
        call = {'agent': agent_name, 'attempt': attempt, 'status': 'started',
                'messages': [{'role': m.type, 'name': m.name, 'content': m.content} for m in messages]}
        if MODEL_CALLS.get() is not None:
            MODEL_CALLS.get().append(call)
        token = CURRENT_CALL.set(call)
        started = time.perf_counter()
        try:
            log_model_call(agent_name, messages)
            started = time.perf_counter()
            options = dict(kwargs)
            if REASONING_EFFORT:
                options['reasoning'] = {'effort': REASONING_EFFORT}
            response = get_llm().invoke(messages, provider={'allow_fallbacks': False}, **options)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            log_model_response(agent_name, response)
            if isinstance(getattr(response, "response_metadata", None), dict):
                response.response_metadata['latency_ms'] = elapsed_ms
            call['response'] = response.model_dump(mode='json')
            call['usage'] = usage_entry(agent_name, response)
            if call.get('raw_response'):
                raw_usage = json.loads(call['raw_response']).get('usage') or {}
                call['usage']['estimated_cost_usd'] = raw_usage.get('cost')
            finish = (getattr(response, 'response_metadata', {}) or {}).get('finish_reason')
            if finish not in (None, 'stop'):
                raise ValueError(f'model response did not finish normally: {finish}')
            if not getattr(response, "content", None) or not response.content.strip():
                raise ValueError("model returned an empty response")
            if validator is not None:
                validator(response)
            if isinstance(getattr(response, "response_metadata", None), dict):
                response.response_metadata["latency_ms"] = elapsed_ms
            call['status'] = 'completed'
            return response
        except Exception as error:
            last_error = error
            call.update(status='failed', error=str(error))
            print(f"[{agent_name}] model attempt {attempt}/{MAX_MODEL_RETRIES} failed: {error}", flush=True)
            if attempt < MAX_MODEL_RETRIES:
                delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                print(f"[{agent_name}] retrying in {delay:.1f}s", flush=True)
                time.sleep(delay)
        finally:
            call['latency_ms'] = round((time.perf_counter() - started) * 1000)
            CURRENT_CALL.reset(token)
    raise RuntimeError(f"{agent_name} model failed after {MAX_MODEL_RETRIES} attempts") from last_error


def invoke_analyst(messages, model_client=None, **kwargs):
    if model_client is None:
        model_client = get_llm()
    return model_client.invoke(messages, **kwargs)


def clean_messages(messages):
    cleaned = []

    for message in messages:
        content = message.content
        metadata = {
            "id": getattr(message, "id", None),
            "name": getattr(message, "name", None),
        }

        if message.type == "human":
            cleaned.append(HumanMessage(content=content, **metadata))
        elif message.type == "ai":
            cleaned.append(AIMessage(content=content, **metadata))
        elif message.type == "system":
            cleaned.append(SystemMessage(content=content, **metadata))

    return cleaned


def analyst_agent(state: AgentState):
    print("Analyst Agent Invoked")
    agent_name = "analyst_agent"
    system_prompt = SystemMessage(
        content=(
            ANALYST_SYSTEM_PROMPT
            + NUMERICAL_PRECISION_INSTRUCTIONS
            + "\nReturn only one JSON object matching this schema:\n"
            + json.dumps(Report.model_json_schema())
            + "\nPreserve the current report_id exactly. Do not create or modify it."
            + "\nPreserve claim_ids for retained claims so revisions can be traced.\n"
        )
    )

    packet_message = HumanMessage(
        content=json.dumps({
            "evidence_packet": state["evidence_packet"],
            "current_report": latest_report(state),
            "required_report_id": latest_report(state)["report_id"],
        }, ensure_ascii=False),
        name="benchmark_input",
        id="benchmark:evidence_packet",
    )

    messages_to_send = [system_prompt, packet_message] + clean_messages(state["messages"])

    response = invoke_with_retry(
        agent_name,
        messages_to_send,
        validator=lambda candidate: parse_report_response(candidate.content),
        response_format={"type": "json_object"},
    )
    print("Analyst model response received", flush=True)
    log_model_response(agent_name, response)
    label_message(response, agent_name)
    revised_report = parse_report_response(response.content)
    expected_report_id = latest_report(state)["report_id"]
    if revised_report.report_id != expected_report_id:
        raise ValueError(
            "Analyst changed report_id: "
            f"expected {expected_report_id}, got {revised_report.report_id}"
        )
    report = revised_report.model_dump(mode='json')
    old_claims = {c['claim_id']: c for c in latest_report(state)['claims']}
    new_claims = {c['claim_id']: c for c in report['claims']}
    changes = {'edited_claim_ids': [cid for cid in old_claims.keys() & new_claims.keys() if old_claims[cid] != new_claims[cid]],
               'retracted_claim_ids': sorted(old_claims.keys() - new_claims.keys()),
               'new_claim_ids': sorted(new_claims.keys() - old_claims.keys())}
    print("Analyst report validated and appended", flush=True)
    return {
        "messages": [response],
        "final_reports": append_report(state, report),
        "analyst_revision_turns": [*(state.get("analyst_revision_turns") or []),
                                   {"round": state.get("debate_round", 0), **changes}],
        "usage_log": with_usage(state, agent_name, response),
    }


def risk_manager_agent(state: AgentState):
    print("Risk Manager Agent Invoked")
    agent_name = "risk_manager_agent"
    round_no = state["debate_round"] + 1
    system_prompt = SystemMessage(
        content=(
            RISK_MANAGER_SYSTEM_PROMPT
            + NUMERICAL_PRECISION_INSTRUCTIONS
            + "\nReturn only one JSON object matching this schema:\n"
            + json.dumps(RiskManagerTurn.model_json_schema())
            + "\nUse an empty challenges list if no specific defect is found."
            + "\ntarget_claim_id must be a claim_id from the current report, or null for a rationale error or an omitted claim."
            + " For null targets, identify the disputed assertion or missing evidence in explanation. defect_type must be exactly one of: "
            + ", ".join(CHALLENGE_TYPES)
            + ". evidence_ids may list only evidence_id values from the packet. Do not include challenge_id."
        )
    )
    context_message = HumanMessage(
        content=json.dumps({
            "evidence_packet": state["evidence_packet"],
            "current_report": latest_report(state),
            "analyst_note": analyst_note(state),
            "latest_verifier_report": latest_verifier_report(state),
        }, ensure_ascii=False)
    )
    messages_to_send = [system_prompt, context_message] + clean_messages(state["messages"])

    def validate(candidate):
        check_risk_manager_turn(parse_risk_manager_response(candidate.content), state)

    response = invoke_with_retry(agent_name, messages_to_send, validator=validate,
                                 response_format={"type": "json_object"})
    label_message(response, agent_name)
    print("Risk Manager response received", flush=True)
    log_model_response(agent_name, response)
    turn = number_challenges(parse_risk_manager_response(response.content), round_no)
    # The Analyst reads the normalized turn, so it can refer to challenges by their IDs.
    response.content = json.dumps(turn, ensure_ascii=False)

    target_message = next(
        (message for message in reversed(state["messages"])
         if message.type == "ai" and getattr(message, "name", "").startswith("analyst")),
        None,
    )
    target_id = getattr(target_message, "id", "unknown")
    feedback = dict(state.get("risk_feedback") or {})
    feedback[target_id] = {
        "agent": agent_name,
        "feedback_message_id": response.id,
        "content": response.content,
    }
    return {
        "messages": [response],
        "risk_feedback": feedback,
        "debate_round": round_no,
        "risk_manager_turns": [*(state.get("risk_manager_turns") or []),
                               {"round": round_no, **turn, "structured": True, "text": response.content}],
        "usage_log": with_usage(state, agent_name, response),
    }


def trader_agent(state: AgentState):
    print("Trader Agent Invoked")
    agent_name = "trader_agent"
    system_prompt = SystemMessage(
        content=(
            TRADER_SYSTEM_PROMPT
            + "\nReturn only one JSON object matching this schema:\n"
            + json.dumps(TraderDecision.model_json_schema())
            + "\nACCEPT means the supplied analysis adequately supports the current recommendation; otherwise REJECT."
            + "\nsupport_score (0-100) describes support in the supplied analysis, not a return forecast or calibrated probability."
            + " relied_on_claim_ids lists the claim_ids your decision rests on."
            + " investment_action must be exactly BUY, HOLD, or SELL."
        )
    )
    context_message = HumanMessage(
        content=(
            "Here is what to use for the decision:\n"
            + json.dumps({
                "current_report": latest_report(state),
                "analyst_note": analyst_note(state),
                "latest_verifier_report": latest_verifier_report(state),
            }, ensure_ascii=False)
            + "\nReturn the required TraderDecision JSON object, and do not include any other text or commentary."
        )
    )
    messages_to_send = [system_prompt, context_message]
    last_ai_message = next((m for m in reversed(state['messages']) if m.type == 'ai'), None)
    if last_ai_message is not None:
        messages_to_send.append(AIMessage(content=last_ai_message.content,
                                         id=last_ai_message.id, name=last_ai_message.name))

    def validate(candidate):
        check_trader_decision(parse_trader_response(candidate.content), state)

    response = invoke_with_retry(agent_name, messages_to_send, validator=validate,
                                 response_format={"type": "json_object"})
    label_message(response, agent_name)
    print("Trader response received", flush=True)
    log_model_response(agent_name, response)
    decision = parse_trader_response(response.content)
    return {
        "messages": [response],
        "trader_verdict": decision.model_dump(mode="json"),
        "usage_log": with_usage(state, agent_name, response),
    }
