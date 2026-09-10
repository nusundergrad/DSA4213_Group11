from typing import Annotated, Sequence, TypedDict, List, Optional  # and any other types you need
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages

class AgentState(TypedDict):
    # 1. Conversation History (WITH REDUCER - auto-appends messages)
    # This is the CORRECT way. It appends, never overwrites.
    messages: Annotated[Sequence[AnyMessage], add_messages]
    
    # 2. Audit Log (Raw reasoning, never sent to the LLM)
    # This is a plain list because YOU manually append to it in each agent.
    # raw_responses: List[dict]  # List of {"agent": "analyst", "response": raw_obj, "reasoning": "..."}
    
    # 3. Business Context (Root-level keys)
    ticker: str
    date: str

    # 4. Debate Control (Root-level keys)
    debate_round: int
    max_debate_rounds: int

    # 5. Confidence Control (Root-level keys)
    confidence_level: str
    confidence_example: str