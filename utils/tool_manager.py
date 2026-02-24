import os
import chainlit as cl
from typing import Dict, Any, Union
from backend.tools import ToolRegistry
from utils.sidebar_helpers import set_sidebar_elements

async def run_tool(name: str, args: Dict[str, Any], registry: ToolRegistry) -> str:
    """
    Registry'den tool'u çeker ve çalıştırır (Async Wrapper).
    Eğer tool 'artifacts' dönerse Sidebar'ı günceller.
    """
    # 1. Tool'u Registry'den iste
    tool = registry.get(name)
    
    if not tool:
        return f"Error: Tool '{name}' not found in registry."

    try:
        # 2. Argüman Hazırlığı
        run_kwargs = {}
        
        if name == "web_search":
            run_kwargs = {"query": args.get("query", "")}
        
        elif name == "data_analyst":
            run_kwargs = {"code": args.get("code", "")}
            
        elif name == "file_writer":
            run_kwargs = {
                "filename": args.get("filename"), 
                "content": args.get("content")
            }

        elif name == "image_analysis":
            img_path = args.get("image_path") or args.get("path")
            
            # --- UUID Hallucination Fix ---
            if (not img_path or not os.path.exists(img_path)):
                last_path = cl.user_session.get("last_image_path")
                if last_path and os.path.exists(last_path):
                    img_path = last_path
                else:
                    return f"Error: Image path '{img_path}' not found and no session image available."
            
            run_kwargs = {
                "image_path": img_path, 
                "prompt": args.get("prompt", "Describe.")
            }
        
        else:
            # Standart dışı bir tool geldiyse, direkt argümanları pasla
            run_kwargs = args

        # 3. Tool'u Thread Pool'da Çalıştır (UI Bloklanmasın)
        # cl.make_async(func) -> async_func
        print(f"🔧 Running tool: {name} with args: {run_kwargs}")
        
        # Tool execution (Blocking ise thread'e al, async ise bekle)
        result = await cl.make_async(tool.run)(**run_kwargs)

        # 4. Sonuç İşleme (Sidebar Kontrolü)
        # Yeni Protokol: { "text": "...", "artifacts": [...] }
        if isinstance(result, dict) and ("artifacts" in result or "text" in result):
            text_output = result.get("text", "")
            artifacts = result.get("artifacts", [])
            
            # Eğer artifact varsa sidebar'a bas
            if artifacts:
                await set_sidebar_elements(f"Tool: {name}", artifacts)
                # Yan panele yönlendirme mesajı ekle (opsiyonel)
                # text_output += "\n(Detaylar yan panelde)"
            
            return text_output

        # Legacy Protokol (Sadece string veya düz dict)
        # Web Search dict döner, onu stringe çevirelim mi?
        if isinstance(result, dict) and name == "web_search":
            # Web Search sonucunu da sidebar'a atalım mı? 
            # Şu anki web_search.py dict dönüyor ama 'artifacts' key'i yok.
            # Onu da güncelleyip 'artifacts' yapısına uydurabiliriz.
            return str(result)

        return str(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Tool Execution Error ({name}): {str(e)}"
