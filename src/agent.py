from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv
if __package__:
    from .state import AgentState
    from .prompts import ANALYST_SYSTEM_PROMPT, RISK_MANAGER_SYSTEM_PROMPT, TRADER_SYSTEM_PROMPT
    from .benchmark.schemas import Report
else:
    from state import AgentState
    from prompts import ANALYST_SYSTEM_PROMPT, RISK_MANAGER_SYSTEM_PROMPT, TRADER_SYSTEM_PROMPT
    from benchmark.schemas import Report
import json
import os
import re
import time
from uuid import uuid4

llm = None
# MODEL_NAME = "openrouter/free"
MODEL_NAME = "nvidia/nemotron-3.5-lightning:free"
MAX_MODEL_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 1.0


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


def latest_verifier_report(state: AgentState) -> dict | None:
    """Return verification only when it belongs to the latest report."""
    report = latest_report(state)
    report_id = report.get("report_id") if report else None
    for verifier_report in reversed(state.get("verifier_reports") or []):
        if verifier_report.get("report_id") == report_id:
            return verifier_report
    return None


def get_llm():
    global llm
    if llm is None:
        load_dotenv(override=True)
        llm = ChatOpenRouter(model=MODEL_NAME, temperature=0)
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
        try:
            log_model_call(agent_name, messages)
            response = get_llm().invoke(messages, **kwargs)
            log_model_response(agent_name, response)
            if not getattr(response, "content", None) or not response.content.strip():
                raise ValueError("model returned an empty response")
            if validator is not None:
                validator(response)
            return response
        except Exception as error:
            last_error = error
            print(f"[{agent_name}] model attempt {attempt}/{MAX_MODEL_RETRIES} failed: {error}", flush=True)
            if attempt < MAX_MODEL_RETRIES:
                delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                print(f"[{agent_name}] retrying in {delay:.1f}s", flush=True)
                time.sleep(delay)
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
        # 1. Build the System Prompt (The Persona/Rules)
    system_prompt = SystemMessage(
        content=(
            ANALYST_SYSTEM_PROMPT
            + "\nReturn only one JSON object matching this schema:\n"
            + json.dumps(Report.model_json_schema())
            + "\nPreserve the current report_id exactly. Do not create or modify it.\n"
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

    cleaned_messages = clean_messages(state["messages"])

    messages_to_send = [
        system_prompt,
        packet_message,
    ] + cleaned_messages

    # print("Messages to send to LLM:", messages_to_send)

    response = invoke_with_retry(
        agent_name,
        messages_to_send,
        validator=lambda candidate: parse_report_response(candidate.content),
        response_format={"type": "json_object"},
    )
    print("Analyst model response received", flush=True)
    log_model_response(agent_name, response)
    print("Analyst response content:", response.content, flush=True)
    label_message(response, agent_name)
    revised_report = parse_report_response(response.content)
    expected_report_id = latest_report(state)["report_id"]
    if revised_report.report_id != expected_report_id:
        raise ValueError(
            "Analyst changed report_id: "
            f"expected {expected_report_id}, got {revised_report.report_id}"
        )
    print("Analyst report validated and appended", flush=True)
    revised_report_data = revised_report.model_dump(mode="json")

    # print(f"Analyst Agent Response: {response.content}")
    
    
    # 5. Return the update (LangGraph appends this to the existing messages)
    return {
        "messages": [response],
        "final_reports": append_report(state, revised_report_data),
    }


    # # Calls the actual OpenAI API with the conversation history
    # response = llm.invoke(state["messages"])
    # # Returns the real AI response
    # return {"messages": [response]}

def risk_manager_agent(state: AgentState):
    print("Risk Manager Agent Invoked")
    agent_name = "risk_manager_agent"
        # 1. Build the System Prompt (The Persona/Rules)
    system_prompt = SystemMessage(
        content=(
            RISK_MANAGER_SYSTEM_PROMPT
        )
    )
    
    # 2. Inject the 10-K context from the state
    context_message = HumanMessage(
        content=(
           json.dumps({
               "evidence_packet": state["evidence_packet"],
               "current_report": latest_report(state),
               "latest_verifier_report": latest_verifier_report(state),
           }, ensure_ascii=False)
        )
    )

    cleaned_messages = clean_messages(state["messages"])
    
    # 3. Combine everything: System + Context + Existing Conversation History
    # The state["messages"] contains the conversation so far (e.g., user questions).
    messages_to_send = [system_prompt, context_message] + cleaned_messages

    # print("Messages to send to LLM:", messages_to_send)


    # 4. Call the LLM
    response = invoke_with_retry(agent_name, messages_to_send)
    label_message(response, agent_name)
    print("Risk Manager response received", flush=True)
    log_model_response(agent_name, response)

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

    # print(f"Risk Manager Agent Response: {response.content}")
    # 5. Return the update (LangGraph appends this to the existing messages)
    return {
        "messages": [response],
        "risk_feedback": feedback,
        "debate_round": state["debate_round"] + 1,
    }


def trader_agent(state: AgentState):
    print("Trader Agent Invoked")
    agent_name = "trader_agent"
        # 1. Build the System Prompt (The Persona/Rules)
    system_prompt = SystemMessage(
        content=(
            TRADER_SYSTEM_PROMPT
        )
    )
    
    # 2. Inject the 10-K context from the state
    context_message = HumanMessage(
        content=(
            "Here is the evidence packet and current report to use for the decision:\n"
            + json.dumps({
                "evidence_packet": state["evidence_packet"],
                "current_report": latest_report(state),
                "latest_verifier_report": latest_verifier_report(state),
            }, ensure_ascii=False)
            + "\n"
            # f"{state['filing_text']}\n\n"
            "You have 50 units of money in this stock, you can sell up to 50 units or buy up to 50 units. "
            "Based on this information, provide your investment action"
            "List 3 to 5 core claims to justify your recommendation."
            "Output your recommendation as BUY or SELL and up to 50 units."
        )
    )

    last_ai_message = next(
        (
            message
            for message in reversed(state["messages"])
            if message.type == "ai"
        ),
        None,
    )

    messages_to_send = [
        system_prompt,
        context_message,
    ]

    if last_ai_message is not None:
        messages_to_send.append(
            AIMessage(
                content=last_ai_message.content,
                id=last_ai_message.id,
                name=last_ai_message.name,
            )
        )

    # print("Messages to send to LLM:", messages_to_send)
    # 3. Combine everything: System + Context + Existing Conversation History
    # The state["messages"] contains the conversation so far (e.g., user questions).
    # messages_to_send = [system_prompt, context_message] + state["messages"]
    
    # 4. Call the LLM
    response = invoke_with_retry(agent_name, messages_to_send)
    label_message(response, agent_name)
    print("Trader response received", flush=True)
    log_model_response(agent_name, response)

    # print(f"Trader Agent Response: {response.content}")
    # 5. Return the update (LangGraph appends this to the existing messages)
    return {"messages": [response]}

