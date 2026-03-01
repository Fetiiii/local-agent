from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class ToolCall(BaseModel):
    """Represents a single tool invocation."""
    name: str = Field(..., description="Name of the tool to call.")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool.")

class AgentAction(BaseModel):
    """
    Schema for the Agent's decision output.
    Supports parallel tool calls and a planning step.
    """
    thought: str = Field(..., description="Detailed reasoning behind the action.")
    plan: Optional[List[str]] = Field(default_factory=list, description="Step-by-step strategy for solving the request.")
    tool_calls: Optional[List[ToolCall]] = Field(default_factory=list, description="List of tools to execute in parallel.")
    final_answer: Optional[str] = Field(None, description="Final response to the user. MUST be null if tool_calls is used.")

    class Config:
        extra = "ignore"
