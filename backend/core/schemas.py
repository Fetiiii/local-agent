from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class ToolCall(BaseModel):
    """Represents a single tool invocation."""
    name: str = Field(..., description="Name of the tool to call.")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool.")

class AgentAction(BaseModel):
    """
    Schema for the Agent's decision output.
    Supports parallel tool calls and an adaptive planning step.
    """
    thought: Optional[str] = Field(None, description="Detailed reasoning behind the action.")
    plan: Optional[List[str]] = Field(default_factory=list, description="Step-by-step strategy — only for multi-step or tool-using tasks; empty for trivial turns.")
    tool_calls: Optional[List[ToolCall]] = Field(default_factory=list, max_length=8, description="List of tools to execute in parallel (max 8). Never repeat the same call.")
    final_answer: Optional[str] = Field(None, description="Final response to the user. MUST be null if tool_calls is used.")

    class Config:
        extra = "ignore"
