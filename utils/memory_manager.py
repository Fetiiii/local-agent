import chainlit as cl
from typing import List, Dict
import json

class MemoryManager:
    def __init__(self, max_recent_messages: int = 10):
        """
        max_recent_messages: The number of raw messages to keep in the context window.
        Older messages will be summarized.
        """
        self.max_recent_messages = max_recent_messages
        self.summary_buffer_size = 5  # Number of messages to accumulate before triggering summarization

    async def get_formatted_history(self, thread_id: str = None) -> List[Dict]:
        """
        Retrieves history, handling summarization if the conversation gets too long.
        Returns: [Summary (System Msg)] + [Recent Messages]
        """
        history = cl.user_session.get("history") or []
        summary = cl.user_session.get("summary") or ""
        
        # Check if we need to summarize
        # If history length exceeds max + buffer, we summarize the overflow
        if len(history) > self.max_recent_messages + self.summary_buffer_size:
            await self._summarize_old_messages()
            # Reload updated state
            history = cl.user_session.get("history")
            summary = cl.user_session.get("summary")

        formatted_messages = []
        
        # 1. Add Summary if exists
        if summary:
            formatted_messages.append({
                "role": "system", 
                "content": f"📝 SUMMARY OF PAST CONVERSATION:\n{summary}\n--- End of Summary ---\n"
            })
        
        # 2. Add Recent Messages (limit to max_recent_messages)
        # Actually, if we summarized correctly, 'history' should already be short enough.
        # But as a safeguard, we take the last N.
        recent_messages = history[-self.max_recent_messages:] if history else []
        formatted_messages.extend(recent_messages)
            
        return formatted_messages

    def add_message(self, role: str, content: str):
        """
        Adds a new message to the session history (Synchronous).
        """
        history = cl.user_session.get("history") or []
        history.append({"role": role, "content": content})
        cl.user_session.set("history", history)

    def clear_memory(self):
        """Resets history and summary."""
        cl.user_session.set("history", [])
        cl.user_session.set("summary", "")

    async def _summarize_old_messages(self):
        """
        Summarizes the oldest part of the conversation and updates the session state.
        """
        print("🧹 Memory Manager: Triggering summarization...")
        history = cl.user_session.get("history") or []
        current_summary = cl.user_session.get("summary") or ""
        
        # Determine which messages to summarize (everything older than max_recent)
        # We want to keep the last 'max_recent_messages' intact.
        # So we summarize: history[:-max_recent_messages]
        
        msgs_to_summarize = history[:-self.max_recent_messages]
        remaining_msgs = history[-self.max_recent_messages:]
        
        if not msgs_to_summarize:
            return

        # Format text for LLM
        conversation_text = ""
        for msg in msgs_to_summarize:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            conversation_text += f"{role}: {content}\n"

        prompt = f"""
        You are a memory manager AI. Your task is to update the summary of a conversation.
        
        Current Summary:
        {current_summary if current_summary else "(No summary yet)"}
        
        New Lines to Add:
        {conversation_text}
        
        INSTRUCTIONS:
        1. Combine the "Current Summary" with the "New Lines".
        2. Create a concise, updated summary that captures key facts, user preferences, and decisions.
        3. Do NOT lose important details like names, file names, or specific requests.
        4. Output ONLY the new summary text.
        """

        # Get Model from session to run the summarization
        model = cl.user_session.get("model")
        if not model:
            print("⚠️ Memory Manager: Model not found in session, skipping summarization.")
            return

        try:
            # We use a simplified generation call (not JSON mode)
            response = await model.generate(
                messages=[{"role": "user", "content": prompt}], 
                stream=False, 
                json_mode=False
            )
            
            new_summary = response.strip()
            print(f"✅ Memory Summarized. Length: {len(new_summary)} chars.")
            
            # Update Session
            cl.user_session.set("summary", new_summary)
            cl.user_session.set("history", remaining_msgs)
            
        except Exception as e:
            print(f"❌ Memory Summarization Failed: {e}")

    @staticmethod
    def convert_thread_to_history(thread_steps: List[Dict]) -> List[Dict]:
        """
        Converts DB thread steps to history format.
        """
        formatted_history = []
        for step in thread_steps:
            if step.get("type") == "user_message":
                formatted_history.append({"role": "user", "content": step.get("output", "")})
            elif step.get("type") == "assistant_message":
                formatted_history.append({"role": "assistant", "content": step.get("output", "")})
        return formatted_history
