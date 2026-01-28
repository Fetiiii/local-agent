"""
Tool registry and base class skeletons.
Each tool module defines a subclass of BaseTool and is registered here.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol


class BaseTool(Protocol):
    name: str
    description: str

    def run(self, **kwargs: Any) -> Any:
        ...


TOOL_REGISTRY: Dict[str, BaseTool] = {}


def register_tool(tool: BaseTool) -> None:
    """Register a tool instance by its name."""
    TOOL_REGISTRY[tool.name] = tool


def get_tool(name: str) -> BaseTool:
    return TOOL_REGISTRY[name]


# Auto-import tool modules so they register themselves.
# Only importing active/safe tools for the V2 Architecture.

from backend.tools import file_loader  
from backend.tools import web_search  
# from backend.tools import python_exec  # Devre dışı (İsteğe bağlı açılabilir)
# from backend.tools import sql_query    # Devre dışı
# from backend.tools import shell_exec   # Kaldırıldı (Güvenlik)
# from backend.tools import planning     # Kaldırıldı (Agent Reasoning'e taşındı)