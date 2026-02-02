# utils/helpers.py
import json
import re
import chainlit as cl
from typing import Dict, Optional, Any

def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """JSON veya Python Code Block yakalar ve doğrular."""
    text = text.strip()
    
    # 1. Temiz JSON kontrolü
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Markdown JSON Bloğu (```json ... ```)
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 3. Fallback: Model direkt Python kodu yazdıysa, onu tool call'a çevir
    code_match = re.search(r"```(?:python)?\s*(.*?)\s*```", text, re.DOTALL)
    if code_match:
        code = code_match.group(1)
        if len(code) > 20 and any(keyword in code for keyword in ["import", "print", "plt.", "pd."]):
            return {
                "thought": "Model generated code directly. Auto-wrapping in data_analyst.",
                "tool_name": "data_analyst",
                "tool_args": {"code": code},
                "final_answer": None
            }

    # 4. Metin içindeki ilk ve son süslü parantez aralığı
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
        
    return None

async def safe_db_call(func, *args, **kwargs):
    """Veritabanı işlemlerini güvenli bir şekilde yürütür ve hataları loglar."""
    try:
        if func and callable(func):
            return func(*args, **kwargs)
        print(f"⚠️ safe_db_call: Function {func} is not callable.")
        return None
    except Exception as e:
        print(f"❌ Database Error: {e}")
        try:
            await cl.Message(content=f"⚠️ Veritabanı Hatası: {str(e)}").send()
        except:
            pass
        return None
