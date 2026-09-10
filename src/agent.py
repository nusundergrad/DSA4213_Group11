from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv
from state import AgentState
from tool import mock_retrieve_10k_filing
from prompts import ANALYST_SYSTEM_PROMPT, ANALYST_CONTEXT_MESSAGE_TEMPLATE, RISK_MANAGER_SYSTEM_PROMPT, RISK_MANAGER_CONTEXT_MESSAGE_TEMPLATE, TRADER_SYSTEM_PROMPT, TRADER_CONTEXT_MESSAGE_TEMPLATE
import json
import os

load_dotenv(override=True)



llm = ChatOpenRouter(model="openrouter/free", temperature=0)


def clean_messages(messages):
    cleaned = []

    for message in messages:
        content = message.content

        if message.type == "human":
            cleaned.append(HumanMessage(content=content))
        elif message.type == "ai":
            cleaned.append(AIMessage(content=content))
        elif message.type == "system":
            cleaned.append(SystemMessage(content=content))

    return cleaned


def analyst_agent(state: AgentState):
    print("Analyst Agent Invoked")
    agent_name = "analyst_agent"
        # 1. Build the System Prompt (The Persona/Rules)
    system_prompt = SystemMessage(
        content=(
            ANALYST_SYSTEM_PROMPT
        )
    )

    filing_data = mock_retrieve_10k_filing.invoke({
        "ticker": state["ticker"],
        "date": state["date"],
    })

    filing_message = HumanMessage(
        content=json.dumps(filing_data, ensure_ascii=False)
    )

    context_message = HumanMessage(
        content=(
            ANALYST_CONTEXT_MESSAGE_TEMPLATE.format(
                ticker=state['ticker'],
                date=state['date']
            )
        )
    )

    cleaned_messages = clean_messages(state["messages"])

    messages_to_send = [
        system_prompt,
        context_message,
        filing_message,
    ] + cleaned_messages

    print("Messages to send to LLM:", messages_to_send)

    response = llm.invoke(messages_to_send)
    response.name = agent_name + "_response"

    print(f"Analyst Agent Response: {response.content}")
    
    
    # 5. Return the update (LangGraph appends this to the existing messages)
    return {"messages": [response]}


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
           RISK_MANAGER_CONTEXT_MESSAGE_TEMPLATE.format(
                ticker=state['ticker'],
                date=state['date']
            )
        )
    )

    cleaned_messages = clean_messages(state["messages"])
    
    # 3. Combine everything: System + Context + Existing Conversation History
    # The state["messages"] contains the conversation so far (e.g., user questions).
    messages_to_send = [system_prompt, context_message] + cleaned_messages

    # print("Messages to send to LLM:", messages_to_send)


    # 4. Call the LLM
    response = llm.invoke(messages_to_send)
    response.name = agent_name + "_response"

    print(f"Risk Manager Agent Response: {response.content}")
    # 5. Return the update (LangGraph appends this to the existing messages)
    return {"messages": [response], "debate_round": state["debate_round"] + 1}


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
            # f"Company Ticker: {state['ticker']}\n\n"
            f"Here is the 10-K filing analysis to make decision on:\n"
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
            AIMessage(content=last_ai_message.content)
        )

    # print("Messages to send to LLM:", messages_to_send)
    # 3. Combine everything: System + Context + Existing Conversation History
    # The state["messages"] contains the conversation so far (e.g., user questions).
    # messages_to_send = [system_prompt, context_message] + state["messages"]
    
    # 4. Call the LLM
    response = llm.invoke(messages_to_send)
    response.name = agent_name + "_response"

    print(f"Trader Agent Response: {response.content}")
    # 5. Return the update (LangGraph appends this to the existing messages)
    return {"messages": [response]}

