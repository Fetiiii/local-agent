"""
Rule-based router to decide between direct LLM calls and tool usage.
Provides keyword and explicit tool triggers with allowlist checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import re

from backend.tools import TOOL_REGISTRY, BaseTool


@dataclass
class RouteDecision:
    use_tool: bool
    tool_name: Optional[str] = None
    rationale: str = ""


class Router:
    """
    Simple router that picks a tool if keywords or explicit triggers match
    and the mode allows. Replace with a learned policy or LLM-based decision
    maker later.
    """

    def __init__(self, allowed_modes: Optional[List[str]] = None, allowed_tools: Optional[List[str]] = None) -> None:
        self.allowed_modes = allowed_modes or ["chat", "coder", "analyst", "agent"]
        self.allowed_tools = set(allowed_tools) if allowed_tools else set(TOOL_REGISTRY.keys())
        # Map tool -> keywords to trigger heuristically
        self.tool_keywords: Dict[str, List[str]] = {
            "web_search": ["search", "google", "web", "ara", "internet"],
            "sql_query": ["sql", "query", "database", "db", "veritaban"],
            "python_exec": ["run code", "python", "script", "kod", "hesapla"],
            "file_loader": ["file", "pdf", "docx", "xlsx", "dosya", "upload"],
            "planning": ["plan", "steps", "todo", "görev", "roadmap"],
            "shell_exec": ["shell", "terminal", "command", "bash", "powershell"],
            "image_analysis": ["image", "photo", "resim", "görsel"],
        }
        # Regex for explicit tool selection: e.g., /tool file_loader: ...
        self.explicit_pattern = re.compile(r"(?:/tool|tool:)\s*([a-zA-Z0-9_]+)", re.IGNORECASE)

    def _explicit_tool(self, message: str) -> Optional[str]:
        match = self.explicit_pattern.search(message)
        if match:
            return match.group(1).lower()
        return None

    def decide(self, message: str, mode: str) -> RouteDecision:
        if mode not in self.allowed_modes:
            return RouteDecision(use_tool=False, rationale="Mode not tool-enabled")

        lower = message.lower()
        # Check explicit tool directive first
        explicit = self._explicit_tool(message)
        if explicit:
            if explicit in self.allowed_tools:
                return RouteDecision(use_tool=True, tool_name=explicit, rationale="explicit tool request")
            return RouteDecision(use_tool=False, rationale=f"tool '{explicit}' not allowed")

        # Keyword-based heuristic
        for tool, keywords in self.tool_keywords.items():
            if tool not in self.allowed_tools:
                continue
            if any(k in lower for k in keywords):
                return RouteDecision(use_tool=True, tool_name=tool, rationale=f"keyword:{tool}")

        return RouteDecision(use_tool=False, rationale="no tool match")

    def run_tool(self, tool_name: str, **kwargs) -> str:
        if tool_name not in self.allowed_tools:
            return f"[tool '{tool_name}' blocked]"
        tool: BaseTool = TOOL_REGISTRY[tool_name]
        result = tool.run(**kwargs)
        return str(result)
