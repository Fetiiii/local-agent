"""Execute short Python snippets in a constrained namespace."""

from __future__ import annotations

import ast
import contextlib
import io
from typing import Any, Dict, Set

from backend.tools import BaseTool, register_tool


class SafeNodeVisitor(ast.NodeVisitor):
    """Rejects imports, attribute access, and other unsafe nodes."""

    banned_nodes = (
        ast.Import,
        ast.ImportFrom,
        ast.Global,
        ast.Nonlocal,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.Lambda,
    )
    banned_names = {"__import__", "eval", "exec", "open", "compile", "globals", "locals", "vars", "exit", "quit"}

    def __init__(self) -> None:
        super().__init__()
        self.errors: Set[str] = set()

    def generic_visit(self, node):
        if isinstance(node, self.banned_nodes):
            self.errors.add(f"Use of {type(node).__name__} is not allowed.")
        if isinstance(node, ast.Attribute):
            self.errors.add("Attribute access is blocked.")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.banned_names:
            self.errors.add(f"Call to {node.func.id} is not allowed.")
        super().generic_visit(node)


class PythonExecTool:
    name = "python_exec"
    description = "Execute short Python snippets in a controlled environment."
    MAX_OUTPUT = 4000
    SAFE_BUILTINS = {
        "range": range,
        "len": len,
        "print": print,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "sorted": sorted,
        "enumerate": enumerate,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "round": round,
    }

    def run(self, code: str, **kwargs: Any) -> Dict[str, Any]:
        src = (kwargs.get("code") or kwargs.get("query") or code or "").strip()
        if not src:
            return {"status": "error", "message": "No code provided."}

        parsed = ast.parse(src, mode="exec")
        visitor = SafeNodeVisitor()
        visitor.visit(parsed)
        if visitor.errors:
            return {"status": "error", "message": "; ".join(sorted(visitor.errors))}
        if "__" in src:
            return {"status": "error", "message": "Dunder access is blocked."}

        stdout = io.StringIO()
        locals_safe: Dict[str, Any] = {}
        globals_safe: Dict[str, Any] = {"__builtins__": self.SAFE_BUILTINS}

        try:
            with contextlib.redirect_stdout(stdout):
                exec(compile(parsed, "<python_exec>", "exec"), globals_safe, locals_safe)
            output = stdout.getvalue().strip()
            if len(output) > self.MAX_OUTPUT:
                output = output[: self.MAX_OUTPUT] + "...(truncated)"
            return {"status": "ok", "output": output, "locals": locals_safe}
        except Exception as e:
            return {"status": "error", "message": str(e)}


register_tool(PythonExecTool())
