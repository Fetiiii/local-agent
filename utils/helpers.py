import json
from typing import Optional, Dict, Any
from json_repair import repair_json
from backend.core.schemas import AgentAction

def safe_db_call(func):
    """Decorator to handle database errors safely."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"❌ Database Error: {e}")
            return None
    return wrapper

def extract_json(response_str: str, schema_cls: Any = AgentAction) -> Optional[Dict[str, Any]]:
    """
    Parses and validates the LLM's JSON response using the given Pydantic schema.
    Handles partial JSON, missing braces, and extra text.
    """
    try:
        print(f"DEBUG: Raw LLM Response: {response_str}")
        # 1. Repair JSON (Handles missing brackets, trailing commas, etc.)
        # json_repair tries to find the JSON object within the text automatically.
        repaired_json_str = repair_json(response_str)
        
        if not repaired_json_str:
            print("⚠️ No valid JSON found in response.")
            return None

        # 2. Parse into Python Dict
        parsed_dict = json.loads(repaired_json_str)

        # BUGFIX: Handle legacy model generations (tool_name instead of tool_calls)
        if "tool_name" in parsed_dict and "tool_calls" not in parsed_dict:
            parsed_dict["tool_calls"] = [{"name": parsed_dict["tool_name"], "args": parsed_dict.get("tool_args", {})}]
            parsed_dict.pop("tool_name", None)
            parsed_dict.pop("tool_args", None)

        # 3. Validate with Pydantic Schema
        if schema_cls == AgentAction:
            action = schema_cls(**parsed_dict)
            return action.model_dump()
        else:
            # For Reflection Agent and generic schemas
            action = schema_cls(**parsed_dict)
            return action.model_dump()

    except Exception as e:
        print(f"❌ JSON Validation Error: {e}")
        # Optional: Return a fallback action or just None
        return None
