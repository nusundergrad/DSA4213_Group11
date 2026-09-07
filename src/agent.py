from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
from state import AgentState
from tool import mock_retrieve_10k_filing
import os

load_dotenv(override=True)



llm = ChatOpenRouter(model="openrouter/free", temperature=0)


def analyst_agent(state: AgentState):
    agent_name = "analyst_agent"
        # 1. Build the System Prompt (The Persona/Rules)
    system_prompt = SystemMessage(
        content=(
            "You are a Senior Financial Analyst at a hedge fund. "
            "Your task is to read the provided 10-K filing excerpt and generate a trade recommendation. "
            "You must cite your sources (e.g., 'Item 7, p.14') for every numerical claim. "
            "Be specific and avoid vague language like 'primarily' or 'mostly'."
        )
    )

    #get data from tool
    filing_data = mock_retrieve_10k_filing(state['ticker'], state['date'])

    
    # 2. Inject the 10-K context from the state
    context_message = HumanMessage(
        content=(
            f"Company Ticker: {state['ticker']}\n\n"
            f"Date: {state['date']}\n\n"
            f"Here is the 10-K filing excerpt to analyze:\n"
            # f"{state['filing_text']}\n\n"
            "Based on this information, provide your investment thesis (BUY, SELL, or HOLD). "
            "List 3 to 5 core claims to justify your recommendation."
        )
    )


    
    # 3. Combine everything: System + Context + Existing Conversation History
    # The state["messages"] contains the conversation so far (e.g., user questions).
    messages_to_send = [system_prompt, context_message, filing_data] + state["messages"]
    
    # 4. Call the LLM
    response = llm.invoke(messages_to_send)

    response.name = agent_name + "_response"


    
    
    # 5. Return the update (LangGraph appends this to the existing messages)
    return {"messages": [response]}


    # # Calls the actual OpenAI API with the conversation history
    # response = llm.invoke(state["messages"])
    # # Returns the real AI response
    # return {"messages": [response]}

def risk_manager_agent(state: AgentState):

    agent_name = "risk_manager_agent"
        # 1. Build the System Prompt (The Persona/Rules)
    system_prompt = SystemMessage(
        content=(
            "You are the Chief Investment Officer (CIO) at a hedge fund."
            "Your task is to make the final execution decision based on the analyst's recommendation."
            "You must cite your sources (e.g., 'Item 7, p.14') for every numerical claim. "
            "Be specific and avoid vague language like 'primarily' or 'mostly'."
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
            "Output your recommendation in a scale between 0 to 100 where each unit represents amount of stock left in your portfolio."
        )
    )
    
    # 3. Combine everything: System + Context + Existing Conversation History
    # The state["messages"] contains the conversation so far (e.g., user questions).
    messages_to_send = [system_prompt, context_message] + state["messages"]
    
    # 4. Call the LLM
    response = llm.invoke(messages_to_send)
    response.name = agent_name = "_response"
    # 5. Return the update (LangGraph appends this to the existing messages)
    return {"messages": [response]}


def trader_agent(state: AgentState):
    agent_name = "trader_agent"
        # 1. Build the System Prompt (The Persona/Rules)
    system_prompt = SystemMessage(
        content=(
            "You are the Chief Investment Officer (CIO) at a hedge fund."
            "Your task is to make the final execution decision based on the analyst's recommendation."
            "You must cite your sources (e.g., 'Item 7, p.14') for every numerical claim. "
            "Be specific and avoid vague language like 'primarily' or 'mostly'."
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
            "Output your recommendation in a scale between 0 to 100 where each unit represents amount of stock left in your portfolio."
        )
    )
    
    # 3. Combine everything: System + Context + Existing Conversation History
    # The state["messages"] contains the conversation so far (e.g., user questions).
    messages_to_send = [system_prompt, context_message] + state["messages"]
    
    # 4. Call the LLM
    response = llm.invoke(messages_to_send)
    response.name = agent_name + "_response"
    # 5. Return the update (LangGraph appends this to the existing messages)
    return {"messages": [response]}

