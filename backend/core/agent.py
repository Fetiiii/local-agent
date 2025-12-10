"""
Skeleton agent implementation for mode-aware routing and tool-orchestrated calls.
Concrete logic and LLM/tool selection to be filled in subsequent steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from backend.core.context_manager import ContextManager
from backend.core.router import Router
from backend.core.model_client import ModelClient
import sqlite3
from backend.database.db import Database
from backend.core.types import AgentMessage


# NOTE: tools are registered on import; ensure backend.tools package is imported elsewhere on startup.


@dataclass
class AgentConfig:
    default_mode: str = "chat"
    max_history_messages: int = 20
    summary_after_messages: int = 50


class Agent:
    def __init__(
        self,
        model_client: ModelClient,
        context_manager: ContextManager,
        router: Optional[Router] = None,
        db: Optional[Database] = None,
        config: Optional[AgentConfig] = None,
    ) -> None:
        self.model_client = model_client
        self.context = context_manager
        self.config = config or AgentConfig()
        self.router = router or Router()
        self.db = db

    def handle_user_message(
        self, message: str, mode: Optional[str] = None, conversation_id: Optional[int] = None, user_meta: Optional[dict] = None
    ) -> AgentMessage:
        """
        Entry point: takes raw user text, builds context, and decides between direct LLM
        or tool-augmented response. The heuristics are placeholders for now.
        """
        if conversation_id and self.db and not self.context.history:
            self._load_history_from_db(conversation_id)

        active_mode = mode or self.config.default_mode
        history = self.context.get_recent_history(
            limit=self.config.max_history_messages
        )
        trimmed_history = self.context.trim_history(history)

        decision = self.router.decide(message, active_mode)

        user_msg = AgentMessage(role="user", content=message, meta=user_meta or {})
        tool_meta = {"used": False}
        if decision.use_tool and decision.tool_name:
            tool_output = self.router.run_tool(decision.tool_name, query=message)
            tool_output_str = str(tool_output)
            if len(tool_output_str) > 400:
                tool_output_str = tool_output_str[:400] + "...(truncated)"
            tool_meta = {
                "used": True,
                "name": decision.tool_name,
                "rationale": decision.rationale,
                "output": tool_output_str,
            }
            llm_input = trimmed_history + [
                user_msg,
                AgentMessage(
                    role="tool",
                    content=tool_output,
                    meta={"tool": decision.tool_name, "rationale": decision.rationale},
                ),
            ]
        else:
            llm_input = trimmed_history + [user_msg]

        response_text = self.model_client.generate(
            messages=[m.__dict__ for m in llm_input], mode=active_mode
        )

        response = AgentMessage(role="assistant", content=response_text, meta={"tool": tool_meta})
        self.context.append_message(user_msg)
        self.context.append_message(response)

        if self.db and conversation_id:
            try:
                self.db.add_message(conversation_id, user_msg.role, user_msg.content, user_msg.meta)
                self.db.add_message(conversation_id, response.role, response.content, response.meta)
            except sqlite3.IntegrityError:
                # conversation missing; create and retry
                conv_id = self.db.create_conversation(title="Recovered Chat", mode=mode or self.config.default_mode)
                self.db.add_message(conv_id, user_msg.role, user_msg.content, user_msg.meta)
                self.db.add_message(conv_id, response.role, response.content, response.meta)
                if conversation_id != conv_id:
                    conversation_id = conv_id

        return response

    # Additional planning / ReAct hooks can be added here to orchestrate multi-step tool calls.

    def _load_history_from_db(self, conversation_id: int) -> None:
        if not self.db:
            return
        rows = self.db.get_messages(conversation_id, limit=self.config.max_history_messages)
        messages = [
            AgentMessage(role=row["role"], content=row["content"], meta=row.get("meta", {}))
            for row in rows
        ]
        self.context.set_history(messages)
