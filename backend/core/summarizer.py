"""
Summarizer skeleton to compress long histories into a summary message.
"""

from __future__ import annotations

from typing import List

from backend.core.types import AgentMessage


def summarize_history(messages: List[AgentMessage]) -> AgentMessage:
    """
    Placeholder summarizer. Replace with model-backed summarization.
    """
    content = "TODO: summary of last {} messages".format(len(messages))
    return AgentMessage(role="system", content=content, meta={"type": "summary"})
