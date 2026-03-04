from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class ToolCall(BaseModel):
    """Represents a single tool invocation."""
    name: str = Field(..., description="Name of the tool to call.")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool.")

class AgentAction(BaseModel):
    """
    Schema for the Agent's decision output.
    Supports parallel tool calls, a planning step, and Multi-Agent delegation routing.
    """
    thought: str = Field(..., description="Detailed reasoning behind the action.")
    plan: Optional[List[str]] = Field(default_factory=list, description="Step-by-step strategy for solving the request.")
    route_to: Optional[str] = Field(None, description="In Multi-Agent mode, the sub-agent to delegate to (e.g. 'CoderAgent', 'ResearcherAgent'). Null if using tools or answering directly.")
    instruction: Optional[str] = Field(None, description="In Multi-Agent mode, the specific directive/task snippet for the delegated sub-agent.")
    tool_calls: Optional[List[ToolCall]] = Field(default_factory=list, description="List of tools to execute in parallel. MUST be empty if route_to is used.")
    final_answer: Optional[str] = Field(None, description="Final response to the user. MUST be null if tool_calls or route_to is used.")

    class Config:
        extra = "ignore"
