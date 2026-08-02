import json
import os
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional

PROFILE_PATH = Path("data/memory/user_profile.json")

class UserProfileExtraction(BaseModel):
    user_preferences: List[str] = Field(default_factory=list, description="New coding style, framework, or language preferences mentioned by the user.")
    project_facts: List[str] = Field(default_factory=list, description="Important facts about current projects (paths, stack, architecture goals).")
    correction_rules: List[str] = Field(default_factory=list, description="Correction rules given by the user (e.g., 'always use typing', 'never output null').")

class ReflectionAgent:
    """
    Extracts semantic knowledge (Long-Term Memory) from recent conversation summaries
    and updates the persistent user profile graph.
    """
    def __init__(self):
        PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not PROFILE_PATH.exists():
            with open(PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump({"user_preferences": [], "project_facts": [], "correction_rules": []}, f, indent=4)

    def load_profile(self) -> dict:
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"user_preferences": [], "project_facts": [], "correction_rules": []}

    def save_profile(self, data: dict):
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def format_profile_for_prompt(self) -> str:
        profile = self.load_profile()
        rules = profile.get("correction_rules", [])
        prefs = profile.get("user_preferences", [])
        facts = profile.get("project_facts", [])
        
        output = []
        if rules:
            output.append("=== USER CORRECTION RULES ===")
            output.extend([f"- {r}" for r in rules])
        if prefs:
            output.append("=== USER PREFERENCES ===")
            output.extend([f"- {p}" for p in prefs])
        if facts:
            output.append("=== KNOWN PROJECT FACTS ===")
            output.extend([f"- {f}" for f in facts])
            
        return "\n".join(output)

    async def extract_and_update(self, new_conversation_text: str, model=None):
        """Runs the Reflection logic to extract JSON schema facts and append them."""
        print("🧠 Reflection Agent: Extracting long-term semantic knowledge from summary...")
        if model is None:
            # Backward-compat: fall back to the Chainlit session model if present.
            try:
                import chainlit as cl
                model = cl.user_session.get("model")
            except Exception:
                model = None
        if not model:
            print("⚠️ Reflection Agent: Model not found.")
            return

        prompt = f"""You are a Semantic Extraction Agent. Your job is to extract long-term facts about the user and their projects from a recent conversation.

RECENT CONVERSATION SUMMARY to analyze:
{new_conversation_text}

Extract only explicit preferences, project paths/stacks, or strict rules the user commanded.
If there are none, return empty lists.
"""
        
        try:
            generator = await model.generate(
                messages=[{"role": "system", "content": "You MUST output strict JSON only according to the schema requested."},
                          {"role": "user", "content": prompt + "\n\nFormat: {\"user_preferences\": [], \"project_facts\": [], \"correction_rules\": []}"}],
                stream=False,
                json_mode=True,
                schema=UserProfileExtraction.model_json_schema(),
            )
            
            from utils.helpers import extract_json
            extracted = extract_json(generator, schema_cls=UserProfileExtraction)
            
            if extracted:
                current = self.load_profile()
                
                # Deduplication logic
                for key in ["user_preferences", "project_facts", "correction_rules"]:
                    new_items = extracted.get(key, [])
                    if new_items and isinstance(new_items, list):
                        updated_list = list(set(current.get(key, []) + new_items))
                        current[key] = updated_list
                        
                self.save_profile(current)
                print("✅ Reflection Agent: User profile updated with new semantic facts.")
            else:
                print("⚠️ Reflection Agent: No valid JSON extracted.")
        except Exception as e:
            print(f"❌ Reflection Agent Error: {e}")
