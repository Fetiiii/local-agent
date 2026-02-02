# utils/tool_manager.py
import os
import chainlit as cl
from typing import Dict, Any
from backend.tools import ToolRegistry

def run_tool(name: str, args: Dict[str, Any], registry: ToolRegistry) -> str:
    """
    Registry'den tool'u çeker ve çalıştırır.
    """
    # 1. Tool'u Registry'den iste
    tool = registry.get(name)
    
    if not tool:
        return f"Error: Tool '{name}' not found in registry."

    try:
        # 2. Özel Durumlar (Argument Mapping)
        if name == "web_search":
            return str(tool.run(query=args.get("query", "")))
        
        elif name == "data_analyst":
            return tool.run(code=args.get("code", ""))
            
        elif name == "file_writer":
            return tool.run(filename=args.get("filename"), content=args.get("content"))

        elif name == "image_analysis":
            # Image path mantığı (Helper logic)
            img_path = args.get("image_path") or args.get("path")
            
            # --- UUID Hallucination Fix ---
            if (not img_path or not os.path.exists(img_path)):
                last_path = cl.user_session.get("last_image_path")
                if last_path and os.path.exists(last_path):
                    img_path = last_path
                else:
                    return f"Error: Image path '{img_path}' not found and no session image available."
            
            return tool.run(image_path=img_path, prompt=args.get("prompt", "Describe."))

        # Standart dışı bir tool geldiyse, direkt argümanları pasla (Generic Fallback)
        return tool.run(**args)

    except Exception as e:
        return f"Tool Execution Error ({name}): {str(e)}"