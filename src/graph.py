from langgraph.graph import StateGraph, MessagesState, START, END
from agent import analyst_agent, risk_manager_agent, trader_agent
from state import AgentState
import datetime 
from typing import Literal

def agent_debate(state: AgentState, ) -> Literal["analyst_agent", "trader_agent"]:
    if state["debate_round"] < state["max_debate_rounds"]:
        return "analyst_agent"
    return "trader_agent"
def situation_1(input_content: dict):
    graph = StateGraph(AgentState)
    graph.add_node(analyst_agent)
    graph.add_node(risk_manager_agent)
    graph.add_node(trader_agent)
    graph.add_edge(START, "analyst_agent")
    graph.add_edge("analyst_agent", "risk_manager_agent")
    graph.add_conditional_edges(
        "risk_manager_agent",
        agent_debate,
        {"analyst_agent": "analyst_agent", "trader_agent": "trader_agent"},
    )
    graph.add_edge("trader_agent", END)
    graph = graph.compile()

    response = graph.invoke({
        "messages": [
            {
                "role": "user",
                "content": input_content["content"],
            }
        ],
        "ticker": input_content["ticker"],
        "date": input_content["date"],
        "debate_round": input_content["debate_round"],
        "max_debate_rounds": input_content["max_debate_rounds"],
        "confidence_level": input_content["confidence_level"],
        "confidence_example": input_content["confidence_example"],
    })
    # response = graph.invoke({"messages": [{"role": "user", "content": input_content["content"], "ticker": input_content["ticker"], "date": input_content["date"]}]})
    print(response['messages'])
    with open("../output.txt", "a", encoding="utf-8") as file:
        file.write(f"Run {datetime.datetime.now()}\n")
        file.write(str(response['messages']))
        file.write("\n\n")




input_content = {"ticker": "AAPL", "date": "2023", "content": "Run analyst for the following ticker and date", "debate_round": 0, "max_debate_rounds": 1, "confidence_level": "high", "confidence_example": "The company has consistently met or exceeded its earnings targets for the past 5 years."}

# initial_state = {
# }

situation_1(input_content)