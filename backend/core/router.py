"""
Utilities for providing tool definitions and ReAct instructions to the LLM.
Replaces the old keyword-based Router.
"""

from __future__ import annotations
from typing import Optional, Set
from backend.tools import TOOL_REGISTRY

def get_tool_system_prompt(allowed_tools: Optional[Set[str]] = None) -> str:
    """
    Constructs a system prompt section listing available tools and usage format.
    """
    prompt_lines = [
        "## Tools",
        "You have access to the following tools:",
    ]

    for name, tool in TOOL_REGISTRY.items():
        if allowed_tools is not None and name not in allowed_tools:
            continue
        desc = getattr(tool, "description", "No description provided.")
        prompt_lines.append(f"- {name}: {desc}")

    prompt_lines.extend([
        "\n## Instruction",
        "To answer the user's request, use a 'Thought, Action, Action Input, Observation' loop.",
        "1. Thought: specific reasoning about what to do next.",
        "2. Action: the name of the tool to use (must be one of the above).",
        "3. Action Input: the arguments for the tool (JSON format or simple string depending on tool).",
        "4. Observation: the result of the tool (provided by system).",
        "",
        "When you have enough information to answer, use:",
        "Thought: I have sufficient information.",
        "Final Answer: [Your final response to the user]",
        "",
        "Example:",
        "User: What is in file.txt?",
        "Thought: I need to read the file.",
        "Action: file_loader",
        "Action Input: file.txt",
        "Observation: ...content...",
        "Thought: I can now answer.",
        "Final Answer: The file contains...",
    ])

    return "\n".join(prompt_lines)
