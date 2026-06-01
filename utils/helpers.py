import json
import ollama
from typing import Optional, Dict, Any, List
from json_repair import repair_json
from backend.core.schemas import AgentAction

async def get_ollama_models() -> List[str]:
    """Fetches all locally downloaded models from Ollama."""
    try:
        client = ollama.AsyncClient()
        response = await client.list()
        
        # Ollama kütüphanesi versiyonuna göre response bir dict veya obje olabilir
        models_data = []
        if isinstance(response, dict):
            models_data = response.get('models', [])
        else:
            models_data = getattr(response, 'models', [])

        models = []
        for m in models_data:
            # Hem 'model' hem 'name' anahtarlarını/özelliklerini kontrol et
            if isinstance(m, dict):
                name = m.get('model') or m.get('name')
            else:
                name = getattr(m, 'model', None) or getattr(m, 'name', None)
            
            if name:
                models.append(name)

        return sorted(models) if models else ["hf.co/unsloth/gpt-oss-20b-GGUF:Q6_K"]
    except Exception as e:
        print(f"❌ Ollama Model List Error: {e}")
        return ["hf.co/unsloth/gpt-oss-20b-GGUF:Q6_K"]

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
        print(f"[LLM] {response_str[:120]}...")
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
