from langgraph.graph import StateGraph, MessagesState, START, END
from agent import analyst_agent, trader_agent
from state import AgentState    

def situation_1(input_content: dict):
    graph = StateGraph(AgentState)
    graph.add_node(analyst_agent)
    graph.add_node(trader_agent)
    graph.add_edge(START, "analyst_agent")
    graph.add_edge("analyst_agent", "trader_agent")
    graph.add_edge("trader_agent", END)
    graph = graph.compile()

    
    response = graph.invoke({"messages": [{"role": "user", "content": input_content["content"], "ticker": input_content["ticker"], "date": input_content["date"]}]})
    print(response['messages'])


input_content = {"ticker": "AAA", "date": "2023", "content": "Run analyst for the following ticker and date"}

# initial_state = {
# }

situation_1(input_content)