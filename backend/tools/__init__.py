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
from backend.tools import file_loader  # noqa: F401,E402
from backend.tools import web_search  # noqa: F401,E402
from backend.tools import python_exec  # noqa: F401,E402
from backend.tools import sql_query  # noqa: F401,E402
from backend.tools import image_analysis  # noqa: F401,E402
from backend.tools import shell_exec  # noqa: F401,E402
from backend.tools import planning  # noqa: F401,E402
