import asyncio
import os
import sys
import json
from pathlib import Path

# Ensure project root is importable when run directly (python tests/test_memory.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.memory_manager import MemoryManager
from backend.core.rag import RAGManager
from backend.core.reflection_agent import ReflectionAgent
import chainlit as cl

# Mock Chainlit session for testing outside the UI
class MockSession:
    def __init__(self):
        self.store = {}
    def get(self, key, default=None):
        return self.store.get(key, default)
    def set(self, key, value):
        self.store[key] = value

async def test_memory_pipeline():
    print("🚀 Starting Tiered Memory Context Test...\n")
    
    # 1. Setup Mock Environment
    mock_session = MockSession()
    cl.user_session = mock_session
    
    # We need a dummy ModelClient that returns a predictable JSON for Reflection
    # and a predictable string for Summarization, to avoid calling the real LLM in the test.
    class MockModelClient:
        async def generate(self, messages, stream=False, json_mode=False, schema=None):
            if json_mode:
                return '{"user_preferences": ["Prefers Python 3.12", "Always use pytest"], "project_facts": ["Working on a chatbot app in C:\\projects\\chatbot"], "correction_rules": ["Never use print statements in production"]}'
            else:
                return "The user is building a chatbot and prefers Python 3.12. They want to use pytest and avoid print statements."
                
    # Initialize Core Components
    rag = RAGManager()
    model = MockModelClient()
    memory = MemoryManager(max_recent_messages=2) # Set intentionally low (2) so it triggers summary immediately on message 8

    # Set session variables required by MemoryManager and ReflectionAgent
    cl.user_session.set("rag_manager", rag)
    cl.user_session.set("model", model)
    cl.user_session.set("history", [])
    cl.user_session.set("summary", "")

    # 2. Simulate Conversation (Exceeding max buffer to trigger summarization)
    print("💬 Simulating User Conversation...")
    conversation = [
        ("user", "Hi, I'm building a chatbot in C:\\projects\\chatbot."),
        ("assistant", "That sounds like a great project! What stack are you using?"),
        ("user", "I prefer Python 3.12. Also, please always use pytest for testing."),
        ("assistant", "Noted. Python 3.12 and pytest."),
        ("user", "One strict rule: never use print statements in the production code."),
        ("assistant", "Understood. I will use logging instead of print in production."),
        ("user", "Okay, let's write the first component."),
        ("assistant", "Sure, what component?"),
        # The buffer size is max_recent(2) + buffer(5) = 7. Adding the 8th message triggers summary.
        ("user", "Can you scaffold the basic folder structure?") 
    ]

    for role, content in conversation:
         memory.add_message(role, content)
    
    print("\n⏳ Triggering background summarization (now an explicit, non-blocking step)...")
    assert memory.needs_summarization(), "history should be long enough to summarize"
    await memory._run_background_summarization()
    # get_formatted_history is now fast/non-blocking — verify it still returns context
    await memory.get_formatted_history()

    # 3. Verify Short-Term Memory
    print("\n--- TEST: SHORT-TERM MEMORY ---")
    history = cl.user_session.get("history")
    print(f"Remaining History Length: {len(history)} (Should be trimmed down to {memory.max_recent_messages})")
    
    summary = cl.user_session.get("summary")
    print(f"New Summary String generated: '{summary[:50]}...'")

    # 4. Verify Episodic Memory (ChromaDB)
    print("\n--- TEST: EPISODIC MEMORY (ChromaDB) ---")
    print("Searching RAG for episodic context related to 'pytest'...")
    results = rag.search("pytest", n_results=1)
    if results:
        print("✅ Found Episodic Memory Record!")
        print(f"Content:\n{results[0]}")
    else:
        print("❌ Episodic Memory search returned empty.")

    # 5. Verify Long-Term Semantic Memory (Reflection)
    print("\n--- TEST: SEMANTIC LONG-TERM MEMORY (JSON Profile) ---")
    profile_path = Path("data/memory/user_profile.json")
    if profile_path.exists():
        print("✅ user_profile.json exists!")
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print("Extracted Facts:")
            print(json.dumps(data, indent=2))
            
        print("\nChecking formatted prompt injection string:")
        agent = ReflectionAgent()
        print(agent.format_profile_for_prompt())
    else:
        print("❌ user_profile.json was not created.")

if __name__ == "__main__":
    asyncio.run(test_memory_pipeline())
