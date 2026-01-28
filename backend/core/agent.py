"""
Agent implementation with ReAct loop and tool orchestration.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Set

from backend.core.context_manager import ContextManager
from backend.core.model_client import ModelClient
from backend.database.db import Database
from backend.core.types import AgentMessage
from backend.core.router import get_tool_system_prompt
from backend.tools import TOOL_REGISTRY


@dataclass
class AgentConfig:
    default_mode: str = "chat"
    max_history_messages: int = 20
    summary_after_messages: int = 50
    max_react_steps: int = 10


class Agent:
    def __init__(
        self,
        model_client: ModelClient,
        context_manager: ContextManager,
        db: Optional[Database] = None,
        config: Optional[AgentConfig] = None,
    ) -> None:
        self.model_client = model_client
        self.context = context_manager
        self.config = config or AgentConfig()
        self.db = db

    def handle_user_message(
        self,
        message: str,
        mode: Optional[str] = None,
        conversation_id: Optional[int] = None,
        user_meta: Optional[dict] = None,
        allowed_tools: Optional[Set[str]] = None
    ) -> AgentMessage:
        """
        Orchestrates the ReAct loop:
        1. Load history
        2. Inject system prompt with tool definitions
        3. Loop: Generate -> Parse Action -> Execute Tool -> Observe -> Repeat
        4. Return final answer
        """
        if conversation_id and self.db and not self.context.history:
            self._load_history_from_db(conversation_id)

        active_mode = mode or self.config.default_mode
        
        # 1. Prepare Base Context
        history = self.context.get_recent_history(limit=self.config.max_history_messages)
        trimmed_history = self.context.trim_history(history)
        
        # Inject System Prompt for Tools (if tools are allowed)
        # Note: ModelClient might inject its own mode-based system prompt.
        # We append tool instructions as a System message or User-prefix?
        # Typically System message is best.
        tool_prompt = get_tool_system_prompt(allowed_tools)
        system_msg = {"role": "system", "content": tool_prompt}
        
        # Build the initial conversation for LLM
        # We prepend tool prompt to history, or append it? 
        # Ideally: [Mode System Prompt] -> [Tool System Prompt] -> [History] -> [User]
        # ModelClient handles Mode System Prompt. We can pass Tool Prompt as the first "message".
        
        current_messages = [system_msg] + [m.__dict__ for m in trimmed_history]
        
        user_msg = AgentMessage(role="user", content=message, meta=user_meta or {})
        current_messages.append(user_msg.__dict__)
        
        steps_log: List[Dict[str, Any]] = []
        final_answer = ""
        
        # 2. ReAct Loop
        for step in range(self.config.max_react_steps):
            # Generate
            response_text = self.model_client.generate(
                messages=current_messages, 
                mode=active_mode, 
                raw_response=True # We need raw text to parse Actions
            )
            
            # Parse
            decision = self._parse_react_response(response_text)
            
            if decision["action"] == "final":
                final_answer = decision["content"]
                # If we have thoughts, we can log them
                if decision["thought"]:
                    steps_log.append({"type": "thought", "content": decision["thought"]})
                break
            
            elif decision["action"] == "tool":
                tool_name = decision["tool"]
                tool_args = decision["args"]
                thought = decision["thought"]
                
                steps_log.append({"type": "thought", "content": thought})
                
                # Execute Tool
                observation = self._execute_tool(tool_name, tool_args, allowed_tools)
                
                steps_log.append({
                    "type": "tool", 
                    "name": tool_name, 
                    "input": tool_args, 
                    "output": str(observation)[:500] + "..." if len(str(observation)) > 500 else str(observation)
                })
                
                # Append to context
                current_messages.append({"role": "assistant", "content": response_text})
                current_messages.append({"role": "user", "content": f"Observation: {observation}"})
                
            else:
                # No valid action found, treat as final answer or chatter
                final_answer = response_text
                break

        # 3. Finalize
        response = AgentMessage(role="assistant", content=final_answer, meta={"steps": steps_log})
        
        # Save to Context/DB
        self.context.append_message(user_msg)
        self.context.append_message(response)

        if self.db and conversation_id:
            self._save_to_db(conversation_id, user_msg, response)

        return response

    def _parse_react_response(self, text: str) -> Dict[str, Any]:
        """
        Parses text for:
        Action: <tool>
        Action Input: <args>
        """
        # Look for Final Answer
        if "Final Answer:" in text:
            parts = text.split("Final Answer:", 1)
            thought = parts[0].strip()
            answer = parts[1].strip()
            return {"action": "final", "content": answer, "thought": thought}
        
        # Look for Action
        # Regex handles:
        # Action: tool
        # Action Input: input
        # (optional newline)
        action_match = re.search(r"Action:\s*(.+?)\nAction Input:\s*(.+?)(?:\n|$|Observation)", text, re.DOTALL | re.IGNORECASE)
        if action_match:
            return {
                "action": "tool",
                "tool": action_match.group(1).strip(),
                "args": action_match.group(2).strip(),
                "thought": text[:action_match.start()].strip()
            }
            
        return {"action": "final", "content": text, "thought": ""}

    def _execute_tool(self, name: str, args: str, allowed_tools: Optional[Set[str]]) -> str:
        if allowed_tools is not None and name not in allowed_tools:
            return f"Error: Tool '{name}' is not allowed or not available."
        
        tool = TOOL_REGISTRY.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found."
            
        try:
            # Attempt to parse JSON args
            import json
            try:
                if "{" in args and "}" in args:
                    kwargs = json.loads(args)
                    if isinstance(kwargs, dict):
                        return str(tool.run(**kwargs))
            except Exception:
                pass

            # Fallback to simple string query
            return str(tool.run(query=args))
        except Exception as e:
            return f"Error executing tool: {e}"

    def _save_to_db(self, conversation_id: int, user_msg: AgentMessage, assistant_msg: AgentMessage) -> None:
        try:
            self.db.add_message(conversation_id, user_msg.role, user_msg.content, user_msg.meta)
            self.db.add_message(conversation_id, assistant_msg.role, assistant_msg.content, assistant_msg.meta)
        except sqlite3.IntegrityError:
            # Fallback if needed
            pass

    def _load_history_from_db(self, conversation_id: int) -> None:
        if not self.db:
            return
        rows = self.db.get_messages(conversation_id, limit=self.config.max_history_messages)
        messages = [
            AgentMessage(role=row["role"], content=row["content"], meta=row.get("meta", {}))
            for row in rows
        ]
        self.context.set_history(messages)